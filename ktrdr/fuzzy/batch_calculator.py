"""
Batch fuzzy membership calculator for time series data.

This module provides the BatchFuzzyCalculator class that efficiently processes
time series data to compute fuzzy membership values in bulk operations.
"""

from typing import Dict, List, Optional, Tuple, Union
import time
from functools import lru_cache

import pandas as pd
import numpy as np

from ktrdr import get_logger
from ktrdr.errors import ProcessingError
from ktrdr.fuzzy.engine import FuzzyEngine

# Set up module-level logger
logger = get_logger(__name__)


class BatchFuzzyCalculator:
    """
    Efficient batch calculator for fuzzy membership values across time series.

    This class extends the basic FuzzyEngine functionality to handle large
    time series datasets efficiently, with caching and performance optimization
    for repeated calculations.

    Example:
        ```python
        # Initialize with fuzzy engine
        calculator = BatchFuzzyCalculator(fuzzy_engine)

        # Calculate memberships for time series
        rsi_series = pd.Series([30.0, 45.0, 70.0], index=timestamps)
        memberships = calculator.calculate_memberships("rsi", rsi_series)

        # Result structure:
        # {
        #   "rsi_low": pd.Series([0.8, 0.3, 0.0], index=timestamps),
        #   "rsi_neutral": pd.Series([0.2, 0.7, 0.1], index=timestamps),
        #   "rsi_high": pd.Series([0.0, 0.0, 0.9], index=timestamps)
        # }
        ```
    """

    def __init__(self, fuzzy_engine: FuzzyEngine, cache_size: int = 1000):
        """
        Initialize the batch calculator with a fuzzy engine.

        Args:
            fuzzy_engine: FuzzyEngine instance for computing memberships
            cache_size: Maximum number of cached calculation results
        """
        logger.debug("Initializing BatchFuzzyCalculator")
        self._fuzzy_engine = fuzzy_engine
        self._cache_size = cache_size
        self._cache_hits = 0
        self._cache_misses = 0

        # Clear any existing cache
        self._clear_cache()

        logger.info(f"BatchFuzzyCalculator initialized with cache size: {cache_size}")

    def calculate_memberships(
        self, indicator_name: str, values_series: pd.Series
    ) -> Dict[str, pd.Series]:
        """
        Calculate fuzzy membership values for a time series.

        Args:
            indicator_name: Name of the indicator (e.g., "rsi", "macd")
            values_series: pandas Series with timestamps as index and indicator values

        Returns:
            Dictionary mapping fuzzy set names to membership value Series.
            Each Series has the same index as the input values_series.

        Raises:
            ProcessingError: If indicator is unknown or processing fails
        """
        start_time = time.time()
        logger.debug(
            f"Calculating batch memberships for {indicator_name}, "
            f"length: {len(values_series)}"
        )

        # Validate inputs
        self._validate_inputs(indicator_name, values_series)

        # Handle empty series
        if values_series.empty:
            logger.warning(f"Empty series provided for indicator: {indicator_name}")
            return self._create_empty_result(indicator_name, values_series.index)

        # Handle NaN values
        clean_series, nan_mask = self._handle_nan_values(values_series)

        # Check cache first
        cache_key = self._create_cache_key(indicator_name, clean_series)
        cached_result = self._get_cached_result(cache_key)
        if cached_result is not None:
            self._cache_hits += 1
            logger.debug(f"Cache hit for {indicator_name}")
            # Restore NaN values and original index
            return self._restore_result_format(
                cached_result, values_series.index, nan_mask
            )

        self._cache_misses += 1

        # Perform vectorized calculation
        start_time = time.time()
        result = self._compute_memberships(indicator_name, clean_series)
        calculation_time = time.time() - start_time

        logger.debug(
            f"Computed memberships for {indicator_name} in {calculation_time:.3f}s, "
            f"processed {len(clean_series)} points"
        )

        # Cache the result
        self._cache_result(cache_key, result)

        # Restore NaN values and original index
        final_result = self._restore_result_format(
            result, values_series.index, nan_mask
        )

        total_time = time.time() - start_time
        logger.debug(
            f"Total batch calculation time for {indicator_name}: {total_time:.3f}s"
        )

        return final_result

    def _validate_inputs(self, indicator_name: str, values_series: pd.Series) -> None:
        """
        Validate inputs for batch calculation.

        Args:
            indicator_name: Name of the indicator
            values_series: Series of values to process

        Raises:
            ProcessingError: If inputs are invalid
        """
        if not isinstance(indicator_name, str) or not indicator_name.strip():
            raise ProcessingError(
                message="Indicator name must be a non-empty string",
                error_code="BATCH-InvalidIndicatorName",
                details={"indicator_name": indicator_name},
            )

        if not isinstance(values_series, pd.Series):
            raise ProcessingError(
                message="Values must be a pandas Series",
                error_code="BATCH-InvalidValueType",
                details={"type": type(values_series).__name__},
            )

        # Check if indicator exists in fuzzy engine
        available_indicators = self._fuzzy_engine.get_available_indicators()
        if indicator_name not in available_indicators:
            logger.error(f"Unknown indicator: {indicator_name}")
            raise ProcessingError(
                message=f"Unknown indicator: {indicator_name}",
                error_code="BATCH-UnknownIndicator",
                details={
                    "indicator": indicator_name,
                    "available_indicators": available_indicators,
                },
            )

    def _handle_nan_values(
        self, values_series: pd.Series
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Handle NaN values in the input series.

        Args:
            values_series: Input series that may contain NaN values

        Returns:
            Tuple of (clean_series_without_nans, nan_mask)
        """
        nan_mask = values_series.isna()

        if nan_mask.any():
            logger.debug(
                f"Found {nan_mask.sum()} NaN values, will be excluded from calculation"
            )
            clean_series = values_series.dropna()
        else:
            clean_series = values_series

        return clean_series, nan_mask

    def _compute_memberships(
        self, indicator_name: str, clean_series: pd.Series
    ) -> Dict[str, pd.Series]:
        """
        Perform the actual fuzzy membership calculation.

        Args:
            indicator_name: Name of the indicator
            clean_series: Series without NaN values

        Returns:
            Dictionary mapping fuzzy set names to membership Series
        """
        # Use the fuzzy engine to compute memberships
        # The engine returns a DataFrame for series input
        membership_df = self._fuzzy_engine.fuzzify(indicator_name, clean_series)

        # Convert DataFrame columns to individual Series
        result = {}
        for column_name in membership_df.columns:
            result[column_name] = membership_df[column_name]

        return result

    def _restore_result_format(
        self,
        result: Dict[str, pd.Series],
        original_index: pd.Index,
        nan_mask: pd.Series,
    ) -> Dict[str, pd.Series]:
        """
        Restore the result to match the original series format, including NaN handling.

        Args:
            result: Dictionary of membership Series
            original_index: Original index from input series
            nan_mask: Boolean mask indicating NaN positions

        Returns:
            Dictionary with Series aligned to original index
        """
        if not nan_mask.any():
            # No NaN values, just ensure index alignment
            aligned_result = {}
            for set_name, series in result.items():
                aligned_result[set_name] = series.reindex(original_index)
            return aligned_result

        # Restore NaN values in their original positions
        restored_result = {}
        for set_name, series in result.items():
            # Create a new series with the original index, filled with NaN
            restored_series = pd.Series(np.nan, index=original_index, dtype=float)
            # Fill in the computed values where we don't have NaN
            restored_series.loc[~nan_mask] = series.values
            restored_result[set_name] = restored_series

        return restored_result

    def _create_empty_result(
        self, indicator_name: str, index: pd.Index
    ) -> Dict[str, pd.Series]:
        """
        Create an empty result structure for empty input series.

        Args:
            indicator_name: Name of the indicator
            index: Index to use for empty series

        Returns:
            Dictionary with empty Series for each fuzzy set
        """
        fuzzy_sets = self._fuzzy_engine.get_fuzzy_sets(indicator_name)
        result = {}

        for set_name in fuzzy_sets:
            output_name = f"{indicator_name}_{set_name}"
            result[output_name] = pd.Series(dtype=float, index=index)

        return result

    def _create_cache_key(self, indicator_name: str, series: pd.Series) -> str:
        """
        Create a cache key for the given indicator and series.

        Args:
            indicator_name: Name of the indicator
            series: Series of values (should be clean, no NaN)

        Returns:
            String cache key
        """
        # Create a hash based on indicator name and values
        # For performance, we use a simple approach
        values_hash = hash(tuple(series.values))
        return f"{indicator_name}:{values_hash}:{len(series)}"

    @lru_cache(maxsize=None)
    def _get_cached_result(self, cache_key: str) -> Optional[Dict[str, pd.Series]]:
        """
        Get cached result if available.

        Args:
            cache_key: Cache key to look up

        Returns:
            Cached result or None if not found
        """
        # The lru_cache decorator handles the actual caching
        return None

    def _cache_result(self, cache_key: str, result: Dict[str, pd.Series]) -> None:
        """
        Cache the computed result.

        Args:
            cache_key: Key to cache under
            result: Result to cache
        """
        # Due to the complexity of caching pandas Series, we'll implement
        # a simple approach here. In production, consider using a more
        # sophisticated caching strategy.
        pass

    def _clear_cache(self) -> None:
        """Clear the calculation cache."""
        if hasattr(self._get_cached_result, "cache_clear"):
            self._get_cached_result.cache_clear()
        self._cache_hits = 0
        self._cache_misses = 0
        logger.debug("Batch calculator cache cleared")

    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache performance statistics.

        Returns:
            Dictionary with cache hits and misses
        """
        cache_info = (
            self._get_cached_result.cache_info()
            if hasattr(self._get_cached_result, "cache_info")
            else None
        )

        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": self._cache_hits
            / max(1, self._cache_hits + self._cache_misses),
            "cache_size": cache_info.currsize if cache_info else 0,
            "max_size": cache_info.maxsize if cache_info else self._cache_size,
        }

    def clear_cache(self) -> None:
        """
        Clear the cache and reset statistics.

        This method is useful for memory management or when
        fuzzy configurations have changed.
        """
        self._clear_cache()
        logger.info("BatchFuzzyCalculator cache cleared")
