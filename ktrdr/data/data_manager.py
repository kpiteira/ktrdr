"""
DataManager for managing, validating, and processing OHLCV data.

This module extends the LocalDataLoader with more sophisticated data 
management capabilities, integrity checks, and utilities for detecting 
and handling gaps or missing values in time series data.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any, Set, Callable
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

# Import logging system
from ktrdr import (
    get_logger, 
    log_entry_exit, 
    log_performance, 
    log_data_operation, 
    log_error,
    with_context
)

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

from ktrdr.data.local_data_loader import LocalDataLoader

# Get module logger
logger = get_logger(__name__)


class DataManager:
    """
    Manages, validates, and processes OHLCV data.
    
    This class builds upon LocalDataLoader to provide higher-level data management
    capabilities, including data integrity checks, gap detection, and data repair.
    
    Attributes:
        data_loader: The underlying LocalDataLoader instance
        max_gap_percentage: Maximum allowed percentage of gaps in data
        default_repair_method: Default method for repairing missing values
    """
    
    # Standard timeframe frequencies for resampling and gap detection
    TIMEFRAME_FREQUENCIES = {
        '1m': '1min',
        '5m': '5min',
        '15m': '15min',
        '30m': '30min',
        '1h': '1H',
        '4h': '4H',
        '1d': '1D',
        '1w': '1W',
    }
    
    # Mapping of repair methods to their functions
    REPAIR_METHODS = {
        'ffill': pd.DataFrame.ffill,
        'bfill': pd.DataFrame.bfill,
        'interpolate': pd.DataFrame.interpolate,
        'zero': lambda df: df.fillna(0),
        'mean': lambda df: df.fillna(df.mean()),
        'median': lambda df: df.fillna(df.median()),
        'drop': lambda df: df.dropna(),
    }
    
    def __init__(
        self, 
        data_dir: Optional[str] = None, 
        max_gap_percentage: float = 5.0,
        default_repair_method: str = 'ffill'
    ):
        """
        Initialize the DataManager.
        
        Args:
            data_dir: Path to the directory containing data files.
                     If None, will use the path from configuration.
            max_gap_percentage: Maximum allowed percentage of gaps in data (default: 5.0)
            default_repair_method: Default method for repairing missing values
                                  (default: 'ffill', options: 'ffill', 'bfill', 
                                  'interpolate', 'zero', 'mean', 'median', 'drop')
                
        Raises:
            DataError: If initialization parameters are invalid
        """
        # Validate parameters
        if max_gap_percentage < 0 or max_gap_percentage > 100:
            raise DataError(
                message=f"Invalid max_gap_percentage: {max_gap_percentage}. Must be between 0 and 100.",
                error_code="DATA-InvalidParameter",
                details={"parameter": "max_gap_percentage", "value": max_gap_percentage, "valid_range": "0-100"}
            )
            
        if default_repair_method not in self.REPAIR_METHODS:
            raise DataError(
                message=f"Invalid repair method: {default_repair_method}",
                error_code="DATA-InvalidParameter",
                details={
                    "parameter": "default_repair_method",
                    "value": default_repair_method,
                    "valid_options": list(self.REPAIR_METHODS.keys())
                }
            )
            
        # Initialize the LocalDataLoader
        self.data_loader = LocalDataLoader(data_dir=data_dir)
        
        # Store parameters
        self.max_gap_percentage = max_gap_percentage
        self.default_repair_method = default_repair_method
        
        logger.info(f"Initialized DataManager with max_gap_percentage={max_gap_percentage}%, "
                   f"default_repair_method='{default_repair_method}'")
        
    @log_entry_exit(logger=logger, log_args=True)
    @log_performance(threshold_ms=500, logger=logger)
    def load_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        validate: bool = True,
        repair: bool = False,
        repair_method: Optional[str] = None,
        repair_outliers: bool = True,
        context_window: Optional[int] = None,
        std_threshold: float = 3.0,
        strict: bool = False
    ) -> pd.DataFrame:
        """
        Load data with optional validation and repair.
        
        Args:
            symbol: The trading symbol (e.g., 'EURUSD', 'AAPL')
            timeframe: The timeframe of the data (e.g., '1h', '1d')
            start_date: Optional start date for filtering data
            end_date: Optional end date for filtering data
            validate: Whether to validate data integrity (default: True)
            repair: Whether to repair any detected issues (default: False)
            repair_method: Method to use for repairs (default: use self.default_repair_method)
            repair_outliers: Whether to repair outliers during data repair (default: True)
            context_window: Optional window size for contextual outlier detection
            std_threshold: Number of standard deviations to consider as outlier (default: 3.0)
            strict: If True, raises an exception for integrity issues instead of warning (default: False)
            
        Returns:
            DataFrame containing validated (and optionally repaired) OHLCV data
            
        Raises:
            DataNotFoundError: If the data file is not found
            DataCorruptionError: If data has integrity issues and strict=True
            DataError: For other data-related errors
        """
        # Load data using the LocalDataLoader
        logger.info(f"Loading data for {symbol} ({timeframe})")
        df = self.data_loader.load(symbol, timeframe, start_date, end_date)
        
        # Check if df is None (happens when fallback returns None)
        if df is None:
            raise DataNotFoundError(
                message=f"Data not found for {symbol} ({timeframe})",
                error_code="DATA-FileNotFound",
                details={"symbol": symbol, "timeframe": timeframe}
            )
            
        if validate:
            # Always detect outliers for logging purposes, even if not repairing
            if not repair:
                self.detect_outliers(df, std_threshold=std_threshold, 
                                   context_window=context_window, log_outliers=True)
            
            # Check data integrity
            integrity_issues = self.check_data_integrity(df, timeframe)
            
            if integrity_issues:
                issues_str = ", ".join(integrity_issues)
                if strict:
                    logger.error(f"Data integrity issues found and strict mode enabled: {issues_str}")
                    raise DataCorruptionError(
                        message=f"Data integrity issues found: {issues_str}",
                        error_code="DATA-IntegrityIssue",
                        details={"issues": integrity_issues, "symbol": symbol, "timeframe": timeframe}
                    )
                else:
                    logger.warning(f"Data integrity issues found: {issues_str}")
                    
                    if repair:
                        # Apply repairs if requested
                        method = repair_method or self.default_repair_method
                        df = self.repair_data(df, timeframe, method, 
                                           repair_outliers=repair_outliers, 
                                           context_window=context_window,
                                           std_threshold=std_threshold)
                        logger.info(f"Data repaired using '{method}' method")
        
        logger.debug(f"Successfully loaded and processed {len(df)} rows of data for {symbol} ({timeframe})")
        return df
    
    @log_entry_exit(logger=logger, log_args=True)
    def check_data_integrity(self, df: pd.DataFrame, timeframe: str, is_post_repair: bool = False) -> List[str]:
        """
        Check for common data integrity issues.
        
        Args:
            df: DataFrame containing OHLCV data
            timeframe: The timeframe of the data (e.g., '1h', '1d')
            is_post_repair: Whether this check is done after data repair (default: False)
            
        Returns:
            List of detected integrity issues (empty if no issues found)
        """
        issues = []
        
        # Check for missing values
        missing_values = df.isnull().sum()
        if missing_values.sum() > 0:
            columns_with_missing = [f"{col}({missing_values[col]})" for col in missing_values.index if missing_values[col] > 0]
            issues.append(f"Missing values detected in columns: {', '.join(columns_with_missing)}")
        
        # Check for duplicate timestamps
        if df.index.duplicated().any():
            duplicate_count = df.index.duplicated().sum()
            issues.append(f"Duplicate timestamps detected ({duplicate_count} instances)")
        
        # Check for unsorted index
        if not df.index.is_monotonic_increasing:
            issues.append("Index is not sorted in ascending order")
        
        # Check for invalid OHLC relationships (e.g., low > high)
        invalid_ohlc = ((df['low'] > df['high']) | (df['open'] > df['high']) | 
                        (df['close'] > df['high']) | (df['open'] < df['low']) | 
                        (df['close'] < df['low'])).sum()
        if invalid_ohlc > 0:
            issues.append(f"Invalid OHLC relationships detected ({invalid_ohlc} instances)")
        
        # Check for negative volumes
        neg_volumes = (df['volume'] < 0).sum()
        if neg_volumes > 0:
            issues.append(f"Negative volume values detected ({neg_volumes} instances)")
        
        # Check for gaps in the time series
        gaps = self.detect_gaps(df, timeframe)
        if gaps and len(gaps) > 0:
            gap_percentage = (len(gaps) / len(df)) * 100
            if gap_percentage > self.max_gap_percentage:
                issues.append(f"Excessive gaps detected ({len(gaps)} gaps, {gap_percentage:.2f}%)")
        
        # Check for outliers in price data with increased tolerance after repair
        post_repair_tolerance = 1.0 if is_post_repair else 0.0
        outliers = self.detect_outliers(df, post_repair_tolerance=post_repair_tolerance)
        if outliers > 0:
            issues.append(f"Price outliers detected ({outliers} instances)")
        
        return issues
    
    @log_entry_exit(logger=logger)
    def detect_gaps(
        self, 
        df: pd.DataFrame, 
        timeframe: str,
        gap_threshold: int = 1
    ) -> List[Tuple[datetime, datetime]]:
        """
        Detect gaps in time series data.
        
        Args:
            df: DataFrame containing OHLCV data
            timeframe: The timeframe of the data (e.g., '1h', '1d')
            gap_threshold: Number of consecutive missing periods to consider as a gap
            
        Returns:
            List of (start_time, end_time) tuples representing gaps
        """
        if df.empty or len(df) <= 1:
            return []
        
        # Get the pandas frequency string for this timeframe
        freq = self.TIMEFRAME_FREQUENCIES.get(timeframe)
        if not freq:
            logger.warning(f"Unknown timeframe '{timeframe}', gap detection may be inaccurate")
            # Try to infer the frequency from the data
            freq = pd.infer_freq(df.index)
            if not freq:
                logger.warning("Could not infer frequency from data, using '1D' as fallback")
                freq = '1D'
        
        # Create the expected complete index
        start_date = df.index.min()
        end_date = df.index.max()
        expected_index = pd.date_range(start=start_date, end=end_date, freq=freq)
        
        # Find missing times
        missing_times = expected_index.difference(df.index)
        
        # Group consecutive missing times into gaps
        gaps = []
        if len(missing_times) > 0:
            gap_start = missing_times[0]
            prev_time = gap_start
            
            for i in range(1, len(missing_times)):
                current_time = missing_times[i]
                expected_diff = pd.Timedelta(freq)
                
                # If there's a gap between missing times, this means we have two separate gaps
                if current_time - prev_time > expected_diff:
                    # Record the previous gap
                    gaps.append((gap_start, prev_time))
                    # Start a new gap
                    gap_start = current_time
                
                prev_time = current_time
            
            # Add the last gap
            gaps.append((gap_start, prev_time))
            
            # Filter out gaps that are shorter than the threshold
            gaps = [(start, end) for start, end in gaps 
                    if ((end - start) / pd.Timedelta(freq)) >= gap_threshold]
            
        logger.info(f"Detected {len(gaps)} gaps in data")
        return gaps
    
    @log_entry_exit(logger=logger)
    def detect_outliers(
        self, 
        df: pd.DataFrame, 
        std_threshold: float = 3.0,
        columns: Optional[List[str]] = None,
        post_repair_tolerance: float = 0.0,
        context_window: Optional[int] = None,
        log_outliers: bool = True
    ) -> int:
        """
        Detect outliers in price data using Z-score method, with optional context awareness.
        
        Args:
            df: DataFrame containing OHLCV data
            std_threshold: Number of standard deviations to consider as outlier
            columns: List of columns to check (default: checks all OHLC columns)
            post_repair_tolerance: Additional tolerance for post-repair validation (adds to std_threshold)
            context_window: Optional window size for rolling statistics. If provided, uses a rolling
                           window for contextual outlier detection instead of global statistics.
            log_outliers: Whether to log identified outliers (default: True)
            
        Returns:
            Number of outliers detected
        """
        if df.empty:
            return 0
        
        if columns is None:
            columns = ['open', 'high', 'low', 'close']
            
        # Make sure all requested columns exist in the DataFrame
        columns = [col for col in columns if col in df.columns]
        if not columns:
            logger.warning("No valid columns for outlier detection")
            return 0
        
        # Adjust threshold if post-repair tolerance is specified
        effective_threshold = std_threshold + post_repair_tolerance
        
        outlier_count = 0
        outlier_details = []
        
        for col in columns:
            if context_window and len(df) > context_window:
                # Context-aware detection: Use rolling statistics
                logger.debug(f"Using context-aware outlier detection with window={context_window} for '{col}'")
                
                # Calculate rolling mean and std
                rolling_mean = df[col].rolling(window=context_window, min_periods=3).mean()
                rolling_std = df[col].rolling(window=context_window, min_periods=3).std()
                
                # For the first few rows where rolling stats are NaN, use expanding window
                rolling_mean.iloc[:context_window] = df[col].expanding(min_periods=3).mean().iloc[:context_window]
                rolling_std.iloc[:context_window] = df[col].expanding(min_periods=3).std().iloc[:context_window]
                
                # Replace any remaining NaN with column mean/std to avoid errors
                if rolling_mean.isna().any() or rolling_std.isna().any():
                    col_mean = df[col].mean()
                    col_std = df[col].std()
                    rolling_mean.fillna(col_mean, inplace=True)
                    rolling_std.fillna(col_std, inplace=True)
                    
                # Calculate z-scores using the rolling statistics
                z_scores = np.abs((df[col] - rolling_mean) / rolling_std)
            else:
                # Global detection: Use overall mean and std
                mean = df[col].mean()
                std = df[col].std()
                z_scores = np.abs((df[col] - mean) / std)
            
            # Count outliers
            outliers = z_scores > effective_threshold
            col_outliers = outliers.sum()
            outlier_count += col_outliers
            
            if col_outliers > 0 and log_outliers:
                # Log specific outlier positions
                outlier_indices = df.index[outliers]
                for idx in outlier_indices:
                    value = df.loc[idx, col]
                    z_score = z_scores[df.index == idx].values[0]
                    outlier_details.append(f"{col} at {idx}: {value:.2f} (z-score: {z_score:.2f})")
            
        # Log outlier details
        if outlier_count > 0 and log_outliers:
            logger.warning(f"Detected {outlier_count} outliers in price data:")
            for detail in outlier_details[:10]:  # Limit to 10 outliers in log
                logger.warning(f"  - {detail}")
            if len(outlier_details) > 10:
                logger.warning(f"  ... and {len(outlier_details) - 10} more outliers")
            
        return outlier_count
    
    @log_entry_exit(logger=logger, log_args=True)
    def repair_data(
        self, 
        df: pd.DataFrame, 
        timeframe: str,
        method: str = 'ffill',
        repair_outliers: bool = True,
        context_window: Optional[int] = None,
        std_threshold: float = 3.0
    ) -> pd.DataFrame:
        """
        Repair data issues like missing values, gaps, or outliers.
        
        Args:
            df: DataFrame containing OHLCV data
            timeframe: The timeframe of the data (e.g., '1h', '1d')
            method: Repair method to use (default: 'ffill')
            repair_outliers: Whether to repair detected outliers (default: True)
            context_window: Optional window size for contextual outlier detection
            std_threshold: Number of standard deviations to consider as outlier
            
        Returns:
            Repaired DataFrame
            
        Raises:
            DataError: If an invalid repair method is specified
        """
        if df.empty:
            logger.warning("Cannot repair empty DataFrame")
            return df
        
        df_copy = df.copy()
        logger.info(f"Repairing data using method: {method}")
        
        # Get the repair function
        if method not in self.REPAIR_METHODS:
            raise DataError(
                message=f"Invalid repair method: {method}",
                error_code="DATA-InvalidParameter",
                details={
                    "parameter": "method",
                    "value": method,
                    "valid_options": list(self.REPAIR_METHODS.keys())
                }
            )
            
        repair_func = self.REPAIR_METHODS[method]
        
        # Fix gaps by reindexing to a complete time series
        freq = self.TIMEFRAME_FREQUENCIES.get(timeframe)
        if freq and not df_copy.index.is_monotonic_increasing:
            logger.debug("Sorting index before reindexing")
            df_copy = df_copy.sort_index()
        
        if freq:
            logger.debug(f"Reindexing with frequency {freq}")
            # Create continuous index
            full_idx = pd.date_range(
                start=df_copy.index.min(),
                end=df_copy.index.max(),
                freq=freq
            )
            # Reindex the DataFrame
            df_copy = df_copy.reindex(full_idx)
            
            # Apply the repair method to fill gaps
            df_copy = repair_func(df_copy)
            
            # Special case for interpolate to make it work better with gaps
            if method == 'interpolate':
                df_copy = df_copy.interpolate(method='time')
        else:
            # If we don't have a frequency, just apply the repair to existing data
            df_copy = repair_func(df_copy)
        
        # Fix invalid OHLC relationships
        invalid_rows = ((df_copy['low'] > df_copy['high']) | 
                        (df_copy['open'] > df_copy['high']) | 
                        (df_copy['close'] > df_copy['high']) | 
                        (df_copy['open'] < df_copy['low']) | 
                        (df_copy['close'] < df_copy['low']))
        
        if invalid_rows.any():
            logger.debug(f"Fixing {invalid_rows.sum()} rows with invalid OHLC relationships")
            # Fix invalid rows by adjusting high and low values
            for idx in df_copy[invalid_rows].index:
                row = df_copy.loc[idx]
                # Set high to max of OHLC
                df_copy.at[idx, 'high'] = max(row['open'], row['high'], row['low'], row['close'])
                # Set low to min of OHLC
                df_copy.at[idx, 'low'] = min(row['open'], row['high'], row['low'], row['close'])
                
        # Fix negative volumes
        if (df_copy['volume'] < 0).any():
            logger.debug("Fixing negative volume values")
            df_copy.loc[df_copy['volume'] < 0, 'volume'] = 0
        
        # Handle price outliers if requested
        if repair_outliers:
            columns = ['open', 'high', 'low', 'close']
            
            # Detect outliers with context awareness if specified
            for col in columns:
                if col in df_copy.columns:
                    # Detect outliers using either context-aware or global detection
                    if context_window and len(df_copy) > context_window:
                        # Context-aware outlier detection
                        logger.debug(f"Using context-aware outlier detection with window={context_window} for '{col}'")
                        
                        # Calculate rolling mean and std for each point
                        rolling_mean = df_copy[col].rolling(window=context_window, min_periods=3).mean()
                        rolling_std = df_copy[col].rolling(window=context_window, min_periods=3).std()
                        
                        # Handle the initial window with expanding stats
                        rolling_mean.iloc[:context_window] = df_copy[col].expanding(min_periods=3).mean().iloc[:context_window]
                        rolling_std.iloc[:context_window] = df_copy[col].expanding(min_periods=3).std().iloc[:context_window]
                        
                        # Fill any NaN values
                        col_mean = df_copy[col].mean()
                        col_std = df_copy[col].std()
                        rolling_mean.fillna(col_mean, inplace=True)
                        rolling_std.fillna(col_std, inplace=True)
                        
                        # Detect outliers using rolling stats
                        z_scores = np.abs((df_copy[col] - rolling_mean) / rolling_std)
                        outliers = z_scores > std_threshold
                        
                        # Fix outliers based on local context
                        if outliers.any():
                            logger.debug(f"Fixing {outliers.sum()} outliers in '{col}' column using context-aware approach")
                            for idx in df_copy[outliers].index:
                                # Get local stats for this point
                                local_mean = rolling_mean.loc[idx]
                                local_std = rolling_std.loc[idx]
                                
                                # Cap at local bounds
                                upper_bound = local_mean + (std_threshold * local_std)
                                lower_bound = local_mean - (std_threshold * local_std)
                                
                                value = df_copy.loc[idx, col]
                                if value > upper_bound:
                                    df_copy.at[idx, col] = upper_bound
                                elif value < lower_bound:
                                    df_copy.at[idx, col] = lower_bound
                    else:
                        # Global outlier detection
                        mean = df_copy[col].mean()
                        std = df_copy[col].std()
                        
                        # Identify outliers using Z-score
                        z_scores = np.abs((df_copy[col] - mean) / std)
                        outliers = z_scores > std_threshold
                        
                        if outliers.any():
                            logger.debug(f"Fixing {outliers.sum()} outliers in '{col}' column using global approach")
                            
                            # Cap outliers at threshold * std from mean
                            upper_bound = mean + (std_threshold * std)
                            lower_bound = mean - (std_threshold * std)
                            
                            # Cap high outliers
                            df_copy.loc[(df_copy[col] > upper_bound), col] = upper_bound
                            # Cap low outliers
                            df_copy.loc[(df_copy[col] < lower_bound), col] = lower_bound
        else:
            # Just detect and log outliers without repairing
            outlier_count = self.detect_outliers(df_copy, std_threshold=std_threshold, 
                                              context_window=context_window, log_outliers=True)
            if outlier_count > 0:
                logger.warning(f"Found {outlier_count} outliers but not repairing them (repair_outliers=False)")
        
        # Check integrity after repair
        integrity_issues = self.check_data_integrity(df_copy, timeframe, is_post_repair=True)
        if integrity_issues:
            logger.warning(f"Integrity issues detected post-repair: {', '.join(integrity_issues)}")
        
        # Log summary of changes
        changes = 0
        # Count new rows
        new_rows = len(df_copy) - len(df)
        if new_rows > 0:
            changes += new_rows
            
        # Count modified values in existing rows
        common_index = df.index.intersection(df_copy.index)
        if not common_index.empty:
            # Make sure we're comparing with same columns
            common_columns = list(set(df.columns) & set(df_copy.columns))
            df_common = df.loc[common_index, common_columns]
            df_copy_common = df_copy.loc[common_index, common_columns]
            
            # Calculate the number of changed values
            changes += (df_common != df_copy_common).sum().sum()
            
        logger.info(f"Repair completed: {changes} individual values were modified or added")
        
        return df_copy
    
    @log_entry_exit(logger=logger, log_args=True)
    def get_data_summary(
        self, 
        symbol: str, 
        timeframe: str
    ) -> Dict[str, Any]:
        """
        Get a summary of available data for a symbol and timeframe.
        
        Args:
            symbol: The trading symbol (e.g., 'EURUSD', 'AAPL')
            timeframe: The timeframe of the data (e.g., '1h', '1d')
            
        Returns:
            Dictionary containing data summary information
            
        Raises:
            DataNotFoundError: If the data file is not found
        """
        # Check if file exists
        date_range = self.data_loader.get_data_date_range(symbol, timeframe)
        if date_range is None:
            raise DataNotFoundError(
                message=f"Data not found for {symbol} ({timeframe})",
                error_code="DATA-FileNotFound",
                details={"symbol": symbol, "timeframe": timeframe}
            )
            
        start_date, end_date = date_range
        
        # Load the data
        df = self.data_loader.load(symbol, timeframe)
        
        # Calculate summary statistics
        summary = {
            "symbol": symbol,
            "timeframe": timeframe,
            "start_date": start_date,
            "end_date": end_date,
            "duration": end_date - start_date,
            "days": (end_date - start_date).days,
            "rows": len(df),
            "columns": list(df.columns),
            "missing_values": df.isnull().sum().to_dict(),
            "has_gaps": len(self.detect_gaps(df, timeframe)) > 0,
            "min_price": df['low'].min(),
            "max_price": df['high'].max(),
            "avg_price": df['close'].mean(),
            "total_volume": df['volume'].sum()
        }
        
        logger.info(f"Generated data summary for {symbol} ({timeframe})")
        return summary
    
    @log_entry_exit(logger=logger)
    def merge_data(
        self,
        symbol: str,
        timeframe: str,
        new_data: pd.DataFrame,
        save_result: bool = True,
        overwrite_conflicts: bool = False
    ) -> pd.DataFrame:
        """
        Merge new data with existing data, handling overlaps intelligently.
        
        Args:
            symbol: The trading symbol (e.g., 'EURUSD', 'AAPL')
            timeframe: The timeframe of the data (e.g., '1h', '1d')
            new_data: New data to merge
            save_result: Whether to save the merged result
            overwrite_conflicts: Whether to overwrite existing data in case of conflicts
            
        Returns:
            Merged DataFrame
            
        Raises:
            DataError: For data-related errors
        """
        # Validate new data
        self.data_loader._validate_dataframe(new_data)
        
        try:
            # Try to load existing data
            existing_data = self.data_loader.load(symbol, timeframe)
            logger.info(f"Merging {len(new_data)} rows with existing {len(existing_data)} rows")
            
            # Use concat to combine the DataFrames
            merged_data = pd.concat([existing_data, new_data])
            
            # Count how many unique dates we have before handling duplicates
            total_unique_dates = len(merged_data.index.unique())
            
            # If we have duplicates, handle based on overwrite_conflicts flag
            if merged_data.index.duplicated().any():
                if overwrite_conflicts:
                    logger.info("Overwriting conflicting rows with new data")
                    # Keep the last occurrence of each duplicated index
                    merged_data = merged_data[~merged_data.index.duplicated(keep='last')]
                else:
                    logger.info("Preserving existing data for conflicting rows")
                    # Keep the first occurrence of each duplicated index
                    merged_data = merged_data[~merged_data.index.duplicated(keep='first')]
                
                # Log how many rows were affected by conflicts
                logger.debug(f"Found {len(merged_data.index.unique()) - total_unique_dates} conflicting rows")
            
        except DataNotFoundError:
            # If no existing data, just use the new data
            logger.info(f"No existing data found, using {len(new_data)} rows of new data")
            merged_data = new_data
        
        # Sort the index to ensure chronological order
        merged_data = merged_data.sort_index()
        
        # Save if requested
        if save_result:
            self.data_loader.save(merged_data, symbol, timeframe)
            logger.info(f"Saved merged data with {len(merged_data)} rows")
        
        return merged_data
    
    @log_entry_exit(logger=logger, log_args=True)
    def resample_data(
        self,
        df: pd.DataFrame,
        target_timeframe: str,
        source_timeframe: Optional[str] = None,
        fill_gaps: bool = True,
        agg_functions: Optional[Dict[str, str]] = None
    ) -> pd.DataFrame:
        """
        Resample data to a different timeframe.
        
        Args:
            df: DataFrame to resample
            target_timeframe: Target timeframe (e.g., '1h', '1d')
            source_timeframe: Source timeframe (optional, used for validation)
            fill_gaps: Whether to fill gaps in the resampled data
            agg_functions: Dictionary of aggregation functions by column
                         (default uses standard OHLCV aggregation)
            
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
                    "valid_options": list(self.TIMEFRAME_FREQUENCIES.keys())
                }
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
                        "valid_options": list(self.TIMEFRAME_FREQUENCIES.keys())
                    }
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
            agg_functions = {
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }
        
        # Make sure all columns in agg_functions exist in the DataFrame
        agg_functions = {k: v for k, v in agg_functions.items() if k in df.columns}
        
        try:
            logger.debug(f"Resampling data to {target_timeframe} frequency ({target_freq})")
            # Make sure the index is sorted
            df_sorted = df.sort_index() if not df.index.is_monotonic_increasing else df
            
            # Resample the data
            resampled = df_sorted.resample(target_freq).agg(agg_functions)
            
            # Fill gaps if requested
            if fill_gaps and not resampled.empty:
                logger.debug("Filling gaps in resampled data")
                resampled = self.repair_data(resampled, target_timeframe, method=self.default_repair_method)
            
            logger.info(f"Successfully resampled data from {len(df)} rows to {len(resampled)} rows")
            return resampled
            
        except Exception as e:
            logger.error(f"Error during resampling: {str(e)}")
            raise DataError(
                message=f"Failed to resample data: {str(e)}",
                error_code="DATA-ResampleError",
                details={"target_timeframe": target_timeframe, "error": str(e)}
            ) from e
    
    @log_entry_exit(logger=logger)
    def filter_data_by_condition(
        self,
        df: pd.DataFrame,
        condition: Callable[[pd.DataFrame], pd.Series],
        inverse: bool = False
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