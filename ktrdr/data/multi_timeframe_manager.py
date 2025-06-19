"""
Multi-Timeframe Data Manager for loading and synchronizing data across timeframes.

This module extends the DataManager with multi-timeframe capabilities, implementing
graceful failure handling and data synchronization strategies. It preserves the
existing "dumb IB fetcher, smart DataManager" pattern while adding multi-timeframe
orchestration.

Key Features:
- Graceful degradation when some timeframes unavailable
- Smart DataManager orchestrates multiple IB fetcher calls
- IB Fetcher remains "dumb" - only fetches what it's asked for
- Synthetic data generation as fallback strategy
- Comprehensive error handling and logging
"""

import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any, Set
from datetime import datetime, timedelta
from dataclasses import dataclass
import numpy as np
import pandas as pd

# Import logging system
from ktrdr import (
    get_logger,
    log_entry_exit,
    log_performance,
    log_data_operation,
    log_error,
    with_context,
)
from ktrdr.utils.timezone_utils import TimestampManager

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
)

from ktrdr.data.data_manager import DataManager
from ktrdr.data.external_data_interface import ExternalDataProvider
from ktrdr.data.ib_data_adapter import IbDataAdapter
from ktrdr.data.data_quality_validator import DataQualityValidator
from ktrdr.data.gap_classifier import GapClassifier, GapClassification
from ktrdr.data.timeframe_constants import TimeframeConstants

# Get module logger
logger = get_logger(__name__)


@dataclass
class TimeframeDataResult:
    """Result of multi-timeframe data loading operation."""

    primary_timeframe: str
    available_timeframes: List[str]
    failed_timeframes: List[str]
    data: Dict[str, pd.DataFrame]
    synthetic_timeframes: List[str]
    warnings: List[str]
    load_time: float


@dataclass
class TimeframeConfig:
    """Configuration for multi-timeframe data loading."""

    primary_timeframe: str
    auxiliary_timeframes: List[str]
    periods: int = 200
    enable_synthetic_generation: bool = True
    require_minimum_timeframes: int = 1
    max_retry_attempts: int = 3

    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.primary_timeframe in self.auxiliary_timeframes:
            raise ValueError("Primary timeframe cannot be in auxiliary timeframes")

        if self.periods < 10:
            raise ValueError("Minimum 10 periods required")

        if self.require_minimum_timeframes < 1:
            raise ValueError("Must require at least 1 timeframe")


class MultiTimeframeDataManager(DataManager):
    """
    Extended data manager with multi-timeframe support and graceful failure handling.

    This class extends the base DataManager to support loading and synchronizing data
    across multiple timeframes. It implements graceful degradation strategies when
    some timeframes are unavailable and provides comprehensive error handling.

    Key Design Principles:
    - IB Fetcher stays "dumb" - only fetches what it's asked for
    - DataManager becomes "smart" and handles multi-timeframe orchestration
    - Graceful degradation when some timeframes unavailable
    - Comprehensive logging and error reporting
    """

    # Timeframe multipliers for period calculations (minutes)
    TIMEFRAME_MULTIPLIERS = {
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "1h": 60,
        "4h": 240,
        "1d": 1440,
        "1w": 10080,
        "1M": 43200,
    }

    # Supported timeframe hierarchy (lower to higher)
    TIMEFRAME_HIERARCHY = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"]

    def __init__(
        self,
        data_dir: Optional[str] = None,
        max_gap_percentage: float = 5.0,
        default_repair_method: str = "ffill",
        enable_ib: bool = True,
        enable_synthetic_generation: bool = True,
        cache_size: int = 100,
    ):
        """
        Initialize the Multi-Timeframe Data Manager.

        Args:
            data_dir: Path to the directory containing data files
            max_gap_percentage: Maximum allowed percentage of gaps in data
            default_repair_method: Default method for repairing missing values
            enable_ib: Whether to enable IB integration
            enable_synthetic_generation: Whether to enable synthetic data generation
            cache_size: Maximum number of cached data results
        """
        super().__init__(data_dir, max_gap_percentage, default_repair_method, enable_ib)

        self.enable_synthetic_generation = enable_synthetic_generation
        self.cache_size = cache_size

        # Initialize caches for performance
        self._data_cache: Dict[str, TimeframeDataResult] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._cache_ttl = 300  # 5 minutes TTL

        logger.info("Multi-Timeframe Data Manager initialized")

    def load_multi_timeframe_data(
        self,
        symbol: str,
        config: TimeframeConfig,
    ) -> TimeframeDataResult:
        """
        Load synchronized data across multiple timeframes with graceful failure handling.

        This method orchestrates the loading of data across multiple timeframes while
        maintaining graceful degradation when some timeframes are unavailable.

        Architecture:
        - DataManager orchestrates multiple IB fetcher calls
        - IB Fetcher remains "dumb" - just fetches requested segments
        - Graceful degradation when some timeframes unavailable
        - Synthetic data generation as fallback strategy

        Args:
            symbol: Trading symbol to load data for
            config: TimeframeConfig with loading parameters

        Returns:
            TimeframeDataResult with loaded data and metadata

        Raises:
            DataError: If primary timeframe cannot be loaded
            DataValidationError: If configuration is invalid
        """
        start_time = time.time()

        # Validate inputs
        self._validate_multi_timeframe_config(symbol, config)

        # Check cache first
        cache_key = self._generate_cache_key(symbol, config)
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            logger.info(f"Returning cached multi-timeframe data for {symbol}")
            return cached_result

        # Initialize result tracking
        timeframe_data = {}
        failed_timeframes = []
        synthetic_timeframes = []
        warnings = []

        # Step 1: Load primary timeframe (critical - must succeed)
        try:
            logger.info(
                f"Loading primary timeframe {config.primary_timeframe} for {symbol}"
            )
            primary_data = self._load_single_timeframe(
                symbol, config.primary_timeframe, config.periods
            )
            timeframe_data[config.primary_timeframe] = primary_data
            logger.info(
                f"Successfully loaded primary timeframe {config.primary_timeframe}"
            )

        except Exception as e:
            # Primary timeframe failure is critical
            error_msg = f"Cannot load primary timeframe {config.primary_timeframe} for {symbol}: {e}"
            logger.error(error_msg)
            raise DataError(error_msg) from e

        # Step 2: Load auxiliary timeframes (optional - handle failures gracefully)
        for aux_tf in config.auxiliary_timeframes:
            try:
                logger.info(f"Loading auxiliary timeframe {aux_tf} for {symbol}")

                # Calculate periods needed for this timeframe
                tf_periods = self._calculate_periods_for_timeframe(
                    config.primary_timeframe, aux_tf, config.periods
                )

                aux_data = self._load_single_timeframe(symbol, aux_tf, tf_periods)
                timeframe_data[aux_tf] = aux_data
                logger.info(f"Successfully loaded auxiliary timeframe {aux_tf}")

            except Exception as e:
                failed_timeframes.append(aux_tf)
                warning_msg = (
                    f"Failed to load {aux_tf} data for {symbol}: {e}. "
                    f"Will attempt fallback strategies."
                )
                logger.warning(warning_msg)
                warnings.append(warning_msg)

        # Step 3: Apply fallback strategies for missing timeframes
        if failed_timeframes and config.enable_synthetic_generation:
            logger.info(f"Applying fallback strategies for {failed_timeframes}")

            synthetic_data, synthetic_tfs = self._apply_fallback_strategies(
                timeframe_data, failed_timeframes, config.primary_timeframe
            )

            # Add synthetic data to results
            timeframe_data.update(synthetic_data)
            synthetic_timeframes.extend(synthetic_tfs)

            # Update failed timeframes list
            failed_timeframes = [
                tf for tf in failed_timeframes if tf not in synthetic_data
            ]

        # Step 4: Validate minimum timeframes requirement
        if len(timeframe_data) < config.require_minimum_timeframes:
            raise DataError(
                f"Only {len(timeframe_data)} timeframes available, "
                f"but {config.require_minimum_timeframes} required"
            )

        # Step 5: Synchronize available timeframes
        try:
            synchronized_data = self._synchronize_available_timeframes(
                timeframe_data, config.primary_timeframe
            )
        except Exception as e:
            logger.error(f"Failed to synchronize timeframes: {e}")
            raise DataError(f"Timeframe synchronization failed: {e}") from e

        # Step 6: Create result object
        load_time = time.time() - start_time
        result = TimeframeDataResult(
            primary_timeframe=config.primary_timeframe,
            available_timeframes=list(synchronized_data.keys()),
            failed_timeframes=failed_timeframes,
            data=synchronized_data,
            synthetic_timeframes=synthetic_timeframes,
            warnings=warnings,
            load_time=load_time,
        )

        # Cache result
        self._cache_result(cache_key, result)

        # Log final status
        logger.info(
            f"Multi-timeframe data loading completed for {symbol} in {load_time:.2f}s. "
            f"Available: {result.available_timeframes}, Failed: {failed_timeframes}, "
            f"Synthetic: {synthetic_timeframes}"
        )

        return result

    def _load_single_timeframe(
        self, symbol: str, timeframe: str, periods: int, max_retries: int = 3
    ) -> pd.DataFrame:
        """
        Load data for a single timeframe with retry logic.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe to load
            periods: Number of periods to load
            max_retries: Maximum retry attempts

        Returns:
            DataFrame with OHLCV data

        Raises:
            DataError: If loading fails after all retries
        """
        for attempt in range(max_retries):
            try:
                # Try local data first
                try:
                    data = self.load_data(symbol, timeframe, periods)
                    if len(data) >= 10:  # Minimum viable data
                        return data
                    else:
                        logger.warning(
                            f"Insufficient local data for {symbol} {timeframe}"
                        )
                except (DataNotFoundError, FileNotFoundError):
                    logger.info(f"No local data for {symbol} {timeframe}")

                # Try IB data if enabled
                if self.enable_ib and hasattr(self, "ib_fetcher"):
                    logger.info(
                        f"Fetching {symbol} {timeframe} from IB (attempt {attempt + 1})"
                    )
                    data = self.ib_fetcher.fetch_data(
                        symbol=symbol, timeframe=timeframe, periods=periods
                    )
                    return data
                else:
                    raise DataError(
                        f"No data source available for {symbol} {timeframe}"
                    )

            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(
                    f"Attempt {attempt + 1} failed for {symbol} {timeframe}: {e}"
                )
                time.sleep(1)  # Brief pause before retry

        raise DataError(
            f"Failed to load {symbol} {timeframe} after {max_retries} attempts"
        )

    def _calculate_periods_for_timeframe(
        self, primary_timeframe: str, auxiliary_timeframe: str, primary_periods: int
    ) -> int:
        """
        Calculate how many periods are needed in auxiliary timeframe.

        Args:
            primary_timeframe: Primary timeframe
            auxiliary_timeframe: Auxiliary timeframe
            primary_periods: Periods needed in primary timeframe

        Returns:
            Number of periods needed in auxiliary timeframe
        """
        if auxiliary_timeframe not in self.TIMEFRAME_MULTIPLIERS:
            raise ValueError(f"Unsupported timeframe: {auxiliary_timeframe}")

        if primary_timeframe not in self.TIMEFRAME_MULTIPLIERS:
            raise ValueError(f"Unsupported timeframe: {primary_timeframe}")

        primary_minutes = self.TIMEFRAME_MULTIPLIERS[primary_timeframe]
        aux_minutes = self.TIMEFRAME_MULTIPLIERS[auxiliary_timeframe]

        # Calculate ratio and ensure minimum periods
        ratio = aux_minutes / primary_minutes
        calculated_periods = max(10, int(primary_periods / ratio))

        logger.debug(
            f"Calculated {calculated_periods} periods for {auxiliary_timeframe} "
            f"(ratio: {ratio:.2f}, primary: {primary_periods})"
        )

        return calculated_periods

    def _apply_fallback_strategies(
        self,
        available_data: Dict[str, pd.DataFrame],
        failed_timeframes: List[str],
        primary_timeframe: str,
    ) -> Tuple[Dict[str, pd.DataFrame], List[str]]:
        """
        Apply fallback strategies for missing timeframes.

        Args:
            available_data: Successfully loaded data
            failed_timeframes: Timeframes that failed to load
            primary_timeframe: Primary timeframe

        Returns:
            Tuple of (synthetic_data_dict, synthetic_timeframe_list)
        """
        synthetic_data = {}
        synthetic_timeframes = []

        if not self.enable_synthetic_generation:
            return synthetic_data, synthetic_timeframes

        # Strategy 1: Generate higher timeframes from lower timeframes
        for failed_tf in failed_timeframes:
            synthetic_df = self._try_generate_synthetic_timeframe(
                available_data, failed_tf, primary_timeframe
            )

            if synthetic_df is not None:
                synthetic_data[failed_tf] = synthetic_df
                synthetic_timeframes.append(failed_tf)
                logger.info(f"Generated synthetic data for {failed_tf}")

        # Strategy 2: Log degradation warnings
        if len(available_data) == 1:
            logger.warning(
                "Multi-timeframe analysis degraded to single-timeframe. "
                "Model will use primary timeframe only."
            )

        return synthetic_data, synthetic_timeframes

    def _try_generate_synthetic_timeframe(
        self,
        available_data: Dict[str, pd.DataFrame],
        target_timeframe: str,
        primary_timeframe: str,
    ) -> Optional[pd.DataFrame]:
        """
        Try to generate synthetic data for a target timeframe.

        Args:
            available_data: Available data for synthesis
            target_timeframe: Timeframe to generate
            primary_timeframe: Primary timeframe

        Returns:
            Synthetic DataFrame or None if generation failed
        """
        try:
            # Find the best source timeframe for synthesis
            source_tf = self._find_best_synthesis_source(
                available_data.keys(), target_timeframe
            )

            if source_tf is None:
                return None

            source_data = available_data[source_tf]

            # Generate synthetic data based on timeframe relationship
            if self._is_higher_timeframe(target_timeframe, source_tf):
                return self._synthesize_higher_timeframe(source_data, target_timeframe)
            else:
                # Cannot synthesize lower timeframes from higher ones
                return None

        except Exception as e:
            logger.warning(f"Failed to generate synthetic {target_timeframe}: {e}")
            return None

    def _find_best_synthesis_source(
        self, available_timeframes: List[str], target_timeframe: str
    ) -> Optional[str]:
        """
        Find the best source timeframe for synthesis.

        Args:
            available_timeframes: Available timeframes
            target_timeframe: Target timeframe to synthesize

        Returns:
            Best source timeframe or None
        """
        # Get hierarchy positions
        try:
            target_pos = self.TIMEFRAME_HIERARCHY.index(target_timeframe)
        except ValueError:
            return None

        # Find lower timeframes (can synthesize higher from lower)
        candidates = []
        for tf in available_timeframes:
            try:
                tf_pos = self.TIMEFRAME_HIERARCHY.index(tf)
                if tf_pos < target_pos:  # Lower timeframe
                    candidates.append((tf, tf_pos))
            except ValueError:
                continue

        if not candidates:
            return None

        # Return the highest available lower timeframe
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def _is_higher_timeframe(self, tf1: str, tf2: str) -> bool:
        """Check if tf1 is a higher timeframe than tf2."""
        try:
            pos1 = self.TIMEFRAME_HIERARCHY.index(tf1)
            pos2 = self.TIMEFRAME_HIERARCHY.index(tf2)
            return pos1 > pos2
        except ValueError:
            return False

    def _synthesize_higher_timeframe(
        self, source_data: pd.DataFrame, target_timeframe: str
    ) -> pd.DataFrame:
        """
        Synthesize higher timeframe data from lower timeframe data.

        Args:
            source_data: Source data for synthesis
            target_timeframe: Target timeframe

        Returns:
            Synthesized DataFrame
        """
        # Determine resampling rule
        resample_rule = self._get_resample_rule(target_timeframe)

        # Resample the data
        resampled = (
            source_data.resample(resample_rule)
            .agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            )
            .dropna()
        )

        logger.debug(
            f"Synthesized {len(resampled)} {target_timeframe} bars from source data"
        )

        return resampled

    def _get_resample_rule(self, timeframe: str) -> str:
        """Get pandas resample rule for timeframe."""
        resample_rules = {
            "1m": "1min",
            "5m": "5min",
            "15m": "15min",
            "30m": "30min",
            "1h": "1h",
            "4h": "4h",
            "1d": "1D",
            "1w": "1W",
            "1M": "1M",
        }
        return resample_rules.get(timeframe, "1h")

    def _synchronize_available_timeframes(
        self, data_dict: Dict[str, pd.DataFrame], reference_timeframe: str
    ) -> Dict[str, pd.DataFrame]:
        """
        Synchronize multiple timeframes to reference timeline.

        Args:
            data_dict: Dictionary of timeframe data
            reference_timeframe: Reference timeframe for alignment

        Returns:
            Dictionary of synchronized data
        """
        if reference_timeframe not in data_dict:
            raise ValueError(f"Reference timeframe {reference_timeframe} not in data")

        reference_data = data_dict[reference_timeframe]
        synchronized_data = {reference_timeframe: reference_data}

        # Synchronize other timeframes to reference timeline
        for timeframe, data in data_dict.items():
            if timeframe == reference_timeframe:
                continue

            try:
                aligned_data = self._align_to_reference_timeline(
                    data, reference_data, timeframe
                )
                synchronized_data[timeframe] = aligned_data
            except Exception as e:
                logger.warning(f"Failed to align {timeframe} to reference: {e}")
                # Include original data if alignment fails
                synchronized_data[timeframe] = data

        return synchronized_data

    def _align_to_reference_timeline(
        self, data: pd.DataFrame, reference_data: pd.DataFrame, timeframe: str
    ) -> pd.DataFrame:
        """
        Align data to reference timeline using forward-fill.

        Args:
            data: Data to align
            reference_data: Reference timeline
            timeframe: Timeframe being aligned

        Returns:
            Aligned DataFrame
        """
        # Ensure both have timezone-aware UTC timestamps
        if data.index.tz is None:
            data.index = data.index.tz_localize("UTC")
        elif str(data.index.tz) != "UTC":
            data.index = data.index.tz_convert("UTC")

        if reference_data.index.tz is None:
            reference_data.index = reference_data.index.tz_localize("UTC")
        elif str(reference_data.index.tz) != "UTC":
            reference_data.index = reference_data.index.tz_convert("UTC")

        # Reindex to reference timeline with forward fill
        aligned_data = data.reindex(reference_data.index, method="ffill")

        return aligned_data

    def _validate_multi_timeframe_config(
        self, symbol: str, config: TimeframeConfig
    ) -> None:
        """
        Validate multi-timeframe configuration.

        Args:
            symbol: Trading symbol
            config: TimeframeConfig to validate

        Raises:
            DataValidationError: If configuration is invalid
        """
        if not symbol or not isinstance(symbol, str):
            raise DataValidationError("Symbol must be a non-empty string")

        # Validate timeframes
        all_timeframes = [config.primary_timeframe] + config.auxiliary_timeframes
        for tf in all_timeframes:
            if tf not in self.TIMEFRAME_MULTIPLIERS:
                raise DataValidationError(f"Unsupported timeframe: {tf}")

        # Check for duplicates
        if len(set(all_timeframes)) != len(all_timeframes):
            raise DataValidationError("Duplicate timeframes in configuration")

    def _generate_cache_key(self, symbol: str, config: TimeframeConfig) -> str:
        """Generate cache key for configuration."""
        timeframes_str = f"{config.primary_timeframe}|{'|'.join(sorted(config.auxiliary_timeframes))}"
        return f"{symbol}|{timeframes_str}|{config.periods}"

    def _get_cached_result(self, cache_key: str) -> Optional[TimeframeDataResult]:
        """Get cached result if valid."""
        if cache_key not in self._data_cache:
            return None

        # Check TTL
        if time.time() - self._cache_timestamps[cache_key] > self._cache_ttl:
            del self._data_cache[cache_key]
            del self._cache_timestamps[cache_key]
            return None

        return self._data_cache[cache_key]

    def _cache_result(self, cache_key: str, result: TimeframeDataResult) -> None:
        """Cache result with TTL."""
        # Implement LRU eviction if cache is full
        if len(self._data_cache) >= self.cache_size:
            oldest_key = min(
                self._cache_timestamps.keys(), key=lambda k: self._cache_timestamps[k]
            )
            del self._data_cache[oldest_key]
            del self._cache_timestamps[oldest_key]

        self._data_cache[cache_key] = result
        self._cache_timestamps[cache_key] = time.time()

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._data_cache.clear()
        self._cache_timestamps.clear()
        logger.info("Multi-timeframe data cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_size": len(self._data_cache),
            "max_cache_size": self.cache_size,
            "cache_keys": list(self._data_cache.keys()),
            "oldest_entry_age": (
                time.time() - min(self._cache_timestamps.values())
                if self._cache_timestamps
                else 0
            ),
        }


# Factory function for backward compatibility
def create_multi_timeframe_manager(
    data_dir: Optional[str] = None,
    enable_ib: bool = True,
    enable_synthetic_generation: bool = True,
    **kwargs,
) -> MultiTimeframeDataManager:
    """
    Create a MultiTimeframeDataManager instance.

    Args:
        data_dir: Path to data directory
        enable_ib: Whether to enable IB integration
        enable_synthetic_generation: Whether to enable synthetic data generation
        **kwargs: Additional arguments passed to constructor

    Returns:
        MultiTimeframeDataManager instance
    """
    return MultiTimeframeDataManager(
        data_dir=data_dir,
        enable_ib=enable_ib,
        enable_synthetic_generation=enable_synthetic_generation,
        **kwargs,
    )
