"""
DataProcessor Component

Provides data processing functionality for merging, resampling, and transforming data.
This component was extracted from DataManager to handle data manipulation operations
while preserving all original functionality.

This component handles:
- Data merging with conflict resolution
- Data resampling between timeframes  
- OHLCV aggregation functions
- Data transformation utilities
"""

from typing import Any, Callable, Optional, Union

import pandas as pd

from ktrdr.errors import DataError
from ktrdr.logging import get_logger

logger = get_logger(__name__)


class DataProcessor:
    """
    Component for processing and transforming OHLCV data.
    
    Provides data processing functionality extracted from DataManager
    including merging, resampling, and data transformation operations.
    """

    # Mapping of timeframes to pandas frequency strings
    TIMEFRAME_FREQUENCIES = {
        "1m": "1min",
        "5m": "5min", 
        "15m": "15min",
        "30m": "30min",
        "1h": "1H",
        "4h": "4H", 
        "1d": "1D",
        "1w": "1W",
    }

    # Default OHLCV aggregation functions
    DEFAULT_OHLCV_AGGREGATION = {
        "open": "first",
        "high": "max", 
        "low": "min",
        "close": "last",
        "volume": "sum",
    }

    def __init__(self):
        """Initialize the DataProcessor component."""
        logger.debug("Initialized DataProcessor component")

    def merge_data(
        self,
        existing_data: pd.DataFrame,
        new_data: pd.DataFrame, 
        overwrite_conflicts: bool = False,
        validate_data: bool = True,
    ) -> pd.DataFrame:
        """
        Merge new data with existing data, handling overlaps intelligently.

        This method preserves all functionality from DataManager.merge_data()
        including conflict resolution, duplicate handling, and sorting.

        Args:
            existing_data: Existing DataFrame to merge with
            new_data: New data to merge
            overwrite_conflicts: Whether to overwrite existing data in case of conflicts
            validate_data: Whether to validate DataFrame structure

        Returns:
            Merged DataFrame with conflicts resolved

        Raises:
            DataError: For data-related errors during merging
        """
        if validate_data:
            self._validate_dataframe(new_data)
            if existing_data is not None and not existing_data.empty:
                self._validate_dataframe(existing_data)

        # Handle case where existing_data is None or empty
        if existing_data is None or existing_data.empty:
            logger.info(f"No existing data found, using {len(new_data)} rows of new data")
            return new_data.sort_index()

        logger.info(
            f"Merging {len(new_data)} rows with existing {len(existing_data)} rows"
        )

        # Use concat to combine the DataFrames
        merged_data = pd.concat([existing_data, new_data])

        # Count how many unique dates we have before handling duplicates
        total_unique_dates = len(merged_data.index.unique())

        # If we have duplicates, handle based on overwrite_conflicts flag
        if merged_data.index.duplicated().any():
            if overwrite_conflicts:
                logger.info("Overwriting conflicting rows with new data")
                # Keep the last occurrence of each duplicated index
                merged_data = merged_data[~merged_data.index.duplicated(keep="last")]
            else:
                logger.info("Preserving existing data for conflicting rows") 
                # Keep the first occurrence of each duplicated index
                merged_data = merged_data[~merged_data.index.duplicated(keep="first")]

            # Log how many rows were affected by conflicts
            conflict_count = total_unique_dates - len(merged_data.index.unique())
            if conflict_count > 0:
                logger.debug(f"Found {conflict_count} conflicting rows")

        # Sort the index to ensure chronological order
        merged_data = merged_data.sort_index()

        logger.info(f"Merge completed: {len(merged_data)} total rows")
        return merged_data

    def resample_data(
        self,
        df: pd.DataFrame,
        target_timeframe: str,
        source_timeframe: Optional[str] = None,
        fill_gaps: bool = True,
        agg_functions: Optional[dict[str, str]] = None,
        repair_method: str = "ffill",
    ) -> pd.DataFrame:
        """
        Resample data to a different timeframe.

        This method preserves all functionality from DataManager.resample_data()
        including timeframe validation, aggregation functions, and gap filling.

        Args:
            df: DataFrame to resample
            target_timeframe: Target timeframe (e.g., '1h', '1d')
            source_timeframe: Source timeframe (optional, used for validation)
            fill_gaps: Whether to fill gaps in the resampled data
            agg_functions: Dictionary of aggregation functions by column
                         (default uses standard OHLCV aggregation)
            repair_method: Method for filling gaps if fill_gaps=True

        Returns:
            Resampled DataFrame

        Raises:
            DataError: For resampling-related errors
        """
        if df.empty:
            logger.warning("Cannot resample empty DataFrame")
            return df

        # Validate target_timeframe
        target_freq = self.TIMEFRAME_FREQUENCIES.get(target_timeframe)
        if not target_freq:
            raise DataError(
                message=f"Invalid target timeframe: {target_timeframe}",
                error_code="DATA-InvalidParameter",
                details={
                    "parameter": "target_timeframe",
                    "value": target_timeframe,
                    "valid_options": list(self.TIMEFRAME_FREQUENCIES.keys()),
                },
            )

        # If source_timeframe is provided, validate it
        if source_timeframe:
            source_freq = self.TIMEFRAME_FREQUENCIES.get(source_timeframe)
            if not source_freq:
                raise DataError(
                    message=f"Invalid source timeframe: {source_timeframe}",
                    error_code="DATA-InvalidParameter",
                    details={
                        "parameter": "source_timeframe",
                        "value": source_timeframe,
                        "valid_options": list(self.TIMEFRAME_FREQUENCIES.keys()),
                    },
                )

            # Check if timeframe change makes sense (can only go from smaller to larger)
            source_delta = pd.Timedelta(source_freq)
            target_delta = pd.Timedelta(target_freq)

            if target_delta < source_delta:
                logger.warning(
                    f"Cannot downsample from {source_timeframe} to {target_timeframe} "
                    f"as it would require generating data points"
                )

        # Set default aggregation functions if not provided
        if agg_functions is None:
            agg_functions = self.DEFAULT_OHLCV_AGGREGATION.copy()

        # Make sure all columns in agg_functions exist in the DataFrame
        agg_functions = {k: v for k, v in agg_functions.items() if k in df.columns}

        try:
            logger.debug(
                f"Resampling data to {target_timeframe} frequency ({target_freq})"
            )
            # Make sure the index is sorted
            df_sorted = df.sort_index() if not df.index.is_monotonic_increasing else df

            # Resample the data
            resampled = df_sorted.resample(target_freq).agg(agg_functions)  # type: ignore[arg-type]

            # Fill gaps if requested
            if fill_gaps and not resampled.empty:
                logger.debug("Filling gaps in resampled data")
                resampled = self._fill_gaps(resampled, repair_method)

            logger.info(
                f"Successfully resampled data from {len(df)} rows to {len(resampled)} rows"
            )
            return resampled

        except Exception as e:
            logger.error(f"Error during resampling: {str(e)}")
            raise DataError(
                message=f"Failed to resample data: {str(e)}",
                error_code="DATA-ResampleError", 
                details={"target_timeframe": target_timeframe, "error": str(e)},
            ) from e

    def filter_data_by_condition(
        self,
        df: pd.DataFrame,
        condition: Callable[[pd.DataFrame], pd.Series],
        inverse: bool = False,
    ) -> pd.DataFrame:
        """
        Filter data based on a custom condition function.

        Args:
            df: DataFrame to filter
            condition: Function that takes a DataFrame and returns a boolean Series
            inverse: If True, returns rows that don't match the condition

        Returns:
            Filtered DataFrame
        """
        if df.empty:
            return df

        # Apply the condition
        mask = condition(df)

        # If inverse flag is set, invert the mask
        if inverse:
            mask = ~mask

        # Apply the mask
        result = df[mask]
        logger.info(f"Filtered {len(df) - len(result)} rows out of {len(df)} total")
        return result

    def _validate_dataframe(self, df: pd.DataFrame) -> None:
        """
        Validate DataFrame structure for OHLCV data.

        Args:
            df: DataFrame to validate

        Raises:
            DataError: If DataFrame structure is invalid
        """
        if df.empty:
            return

        # Check for required columns (at least some OHLCV data should be present)
        required_columns = ["open", "high", "low", "close"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            raise DataError(
                message=f"Missing required columns: {missing_columns}",
                error_code="DATA-InvalidStructure",
                details={
                    "missing_columns": missing_columns,
                    "available_columns": list(df.columns),
                    "required_columns": required_columns,
                },
            )

        # Check for datetime index
        if not isinstance(df.index, pd.DatetimeIndex):
            raise DataError(
                message="DataFrame must have a DatetimeIndex",
                error_code="DATA-InvalidIndex",
                details={"index_type": type(df.index).__name__},
            )

        logger.debug("DataFrame validation passed")

    def _fill_gaps(self, df: pd.DataFrame, method: str = "ffill") -> pd.DataFrame:
        """
        Fill gaps in DataFrame using specified method.

        Args:
            df: DataFrame with potential gaps
            method: Fill method ('ffill', 'bfill', 'interpolate', etc.)

        Returns:
            DataFrame with gaps filled
        """
        if df.empty:
            return df

        try:
            if method == "ffill":
                return df.ffill()
            elif method == "bfill":
                return df.bfill()
            elif method == "interpolate":
                return df.interpolate()
            elif method == "zero":
                return df.fillna(0)
            elif method == "mean":
                return df.fillna(df.mean())
            elif method == "median":
                return df.fillna(df.median())
            elif method == "drop":
                return df.dropna()
            else:
                logger.warning(f"Unknown fill method '{method}', using ffill")
                return df.ffill()

        except Exception as e:
            logger.warning(f"Gap filling failed with method '{method}': {e}")
            return df