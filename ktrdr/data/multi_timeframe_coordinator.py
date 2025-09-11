"""
Multi-Timeframe Coordination Service

This service handles complex multi-timeframe data loading and synchronization.
It was extracted from DataManager to separate the concern of temporal coordination
from the core data management primitives.

The MultiTimeframeCoordinator uses DataManager's single-timeframe primitives
to coordinate loading and alignment of multiple timeframes.
"""

from datetime import datetime
from typing import Any, Callable, Optional, Union

import pandas as pd

from ktrdr.async_infrastructure.progress import GenericProgressManager
from ktrdr.async_infrastructure.time_estimation import TimeEstimationEngine
from ktrdr.data.async_infrastructure.data_progress_renderer import DataProgressRenderer
from ktrdr.data.components.timeframe_synchronizer import TimeframeSynchronizer
from ktrdr.errors import DataError, DataValidationError
from ktrdr.logging import get_logger

logger = get_logger(__name__)


class MultiTimeframeCoordinator:
    """
    Coordinates multi-timeframe data loading and synchronization.

    This service orchestrates the complex process of loading multiple timeframes,
    finding common data coverage, and temporally aligning the data for analysis.

    It delegates single-timeframe loading to DataManager while handling the
    coordination logic for multiple timeframes.
    """

    def __init__(self, data_manager):
        """
        Initialize the MultiTimeframeCoordinator.

        Args:
            data_manager: DataManager instance to use for single-timeframe operations
        """
        self.data_manager = data_manager
        logger.debug("Initialized MultiTimeframeCoordinator")

    def load_multi_timeframe_data(
        self,
        symbol: str,
        timeframes: list[str],
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        base_timeframe: str = "1h",
        mode: str = "local",
        validate: bool = True,
        repair: bool = False,
        cancellation_token: Optional[Any] = None,
        progress_callback: Optional[Callable] = None,
    ) -> dict[str, pd.DataFrame]:
        """
        Load OHLCV data for multiple timeframes with temporal alignment.

        This method loads data for multiple timeframes simultaneously and aligns them
        temporally using the base_timeframe as the reference grid. All timeframes
        are synchronized to ensure consistent timestamps for multi-timeframe analysis.

        Args:
            symbol: The trading symbol (e.g., 'EURUSD', 'AAPL')
            timeframes: List of timeframes to load (e.g., ['15m', '1h', '4h'])
            start_date: Optional start date for filtering data
            end_date: Optional end date for filtering data
            base_timeframe: Reference timeframe for alignment (default: '1h')
            mode: Loading mode - 'local', 'tail', 'backfill', 'full'
            validate: Whether to validate data integrity
            repair: Whether to repair any detected issues
            cancellation_token: Optional cancellation token for early termination
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary mapping timeframes to aligned DataFrames
            Format: {timeframe: aligned_ohlcv_dataframe}

        Raises:
            DataError: If loading fails for critical timeframes
            DataValidationError: If base_timeframe not in timeframes list
        """
        if not timeframes:
            raise DataValidationError(
                "At least one timeframe must be specified",
                error_code="MULTI_TF_NO_TIMEFRAMES",
                details={"symbol": symbol, "timeframes": timeframes},
            )

        if base_timeframe not in timeframes:
            raise DataValidationError(
                f"Base timeframe '{base_timeframe}' must be included in timeframes list",
                error_code="MULTI_TF_INVALID_BASE",
                details={
                    "symbol": symbol,
                    "base_timeframe": base_timeframe,
                    "timeframes": timeframes,
                },
            )

        # Initialize GenericProgressManager with DataProgressRenderer
        total_steps = len(timeframes) + 1  # Load each TF + synchronization
        time_engine = TimeEstimationEngine()
        renderer = DataProgressRenderer(time_estimation_engine=time_engine)
        progress_manager = GenericProgressManager(
            callback=progress_callback, renderer=renderer
        )
        progress_manager.start_operation(
            operation_id=f"multi_timeframe_{symbol}",
            total_steps=total_steps,
            context={"symbol": symbol, "timeframes": timeframes},
        )

        # Note: GenericProgressManager doesn't have built-in cancellation
        # Cancellation will be handled at a higher level if needed

        # Dictionary to store loaded data for each timeframe
        timeframe_data = {}
        loading_errors = {}

        # Step 1: Load data for each timeframe
        logger.info(f"Loading data for {len(timeframes)} timeframes: {timeframes}")

        for i, timeframe in enumerate(timeframes):
            try:
                # Note: Check cancellation at higher level if needed
                # GenericProgressManager doesn't have built-in cancellation support

                # Update progress for current timeframe
                progress_manager.update_progress(i, f"Loading {timeframe} data")

                logger.debug(f"Loading {symbol} data for timeframe: {timeframe}")

                # Load data for this timeframe using DataManager's primitive
                tf_data = self.data_manager.load_data(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date,
                    mode=mode,
                    validate=validate,
                    repair=repair,
                    cancellation_token=cancellation_token,
                )

                if tf_data is not None and not tf_data.empty:
                    timeframe_data[timeframe] = tf_data
                    logger.debug(
                        f"Successfully loaded {len(tf_data)} rows for {symbol} {timeframe}"
                    )
                else:
                    logger.warning(f"No data loaded for {symbol} {timeframe}")
                    loading_errors[timeframe] = "No data returned"

            except Exception as e:
                error_msg = f"Failed to load {timeframe} data: {str(e)}"
                logger.error(error_msg)
                loading_errors[timeframe] = error_msg

                # If base timeframe fails, this is critical
                if timeframe == base_timeframe:
                    raise DataError(
                        f"Failed to load base timeframe {base_timeframe} for {symbol}",
                        error_code="MULTI_TF_BASE_LOAD_FAILED",
                        details={
                            "symbol": symbol,
                            "base_timeframe": base_timeframe,
                            "error": str(e),
                        },
                    ) from e

        # Check if we have any data to work with
        if not timeframe_data:
            raise DataError(
                f"Failed to load data for any timeframe for {symbol}",
                error_code="MULTI_TF_NO_DATA_LOADED",
                details={
                    "symbol": symbol,
                    "timeframes": timeframes,
                    "errors": loading_errors,
                },
            )

        # Step 1.5: Find common data coverage intersection across all loaded timeframes
        if len(timeframe_data) > 1:
            common_coverage = self._find_common_data_coverage(timeframe_data, symbol)

            # If we have a meaningful data intersection, rescope all timeframes to it
            if common_coverage["is_sufficient"]:
                logger.info(
                    f"📊 Found common data coverage: {common_coverage['start_date']} to {common_coverage['end_date']} "
                    f"({common_coverage['days']} days, {common_coverage['min_bars']} min bars across timeframes)"
                )

                # Rescope all timeframes to the common coverage window
                rescoped_data = {}
                for tf, df in timeframe_data.items():
                    rescoped_df = df.loc[
                        common_coverage["start_date"] : common_coverage["end_date"]
                    ]
                    rescoped_data[tf] = rescoped_df
                    logger.debug(f"  {tf}: {len(rescoped_df)} bars (was {len(df)})")

                timeframe_data = rescoped_data

                # Add a warning to surface to the user
                coverage_warning = (
                    f"⚠️ Multi-timeframe training rescoped to common data coverage: "
                    f"{common_coverage['start_date']:%Y-%m-%d} to {common_coverage['end_date']:%Y-%m-%d} "
                    f"({common_coverage['days']} days). Some requested data outside this window was excluded."
                )
                logger.warning(coverage_warning)

            else:
                # Insufficient common coverage - this is a real problem
                insufficient_msg = (
                    f"❌ Insufficient common data coverage across timeframes. "
                    f"Common window: {common_coverage.get('days', 0)} days, "
                    f"Min bars: {common_coverage.get('min_bars', 0)} "
                    f"(need at least 50 bars for indicators + training)"
                )
                logger.error(insufficient_msg)
                raise DataError(
                    "Multi-timeframe training requires overlapping data across timeframes",
                    error_code="MULTI_TF_INSUFFICIENT_COVERAGE",
                    details={
                        "symbol": symbol,
                        "timeframes": list(timeframe_data.keys()),
                        "common_coverage": common_coverage,
                        "recommendation": "Use longer date range or timeframes with better data availability",
                    },
                )

        # Check if we have the base timeframe (after potential rescoping)
        if base_timeframe not in timeframe_data:
            available_timeframes = list(timeframe_data.keys())
            if available_timeframes:
                logger.warning(
                    f"Base timeframe {base_timeframe} failed to load, using {available_timeframes[0]} as reference"
                )
                base_timeframe = available_timeframes[0]
            else:
                raise DataError(
                    f"No timeframes successfully loaded for {symbol}",
                    error_code="MULTI_TF_NO_SUCCESSFUL_LOADS",
                    details={"symbol": symbol, "errors": loading_errors},
                )

        # Step 2: Synchronize timeframes using TimeframeSynchronizer
        progress_manager.update_progress(len(timeframes), "Synchronizing timeframes")

        try:
            synchronizer = TimeframeSynchronizer()
            aligned_data, sync_stats = synchronizer.synchronize_multiple_timeframes(
                timeframe_data, base_timeframe
            )

            logger.info(
                f"Multi-timeframe synchronization completed: "
                f"{sync_stats.successfully_aligned}/{sync_stats.total_timeframes} timeframes aligned "
                f"(avg quality: {sync_stats.average_quality_score:.3f})"
            )

            # Final progress update
            # Complete the operation
            progress_manager.complete_operation()

            if loading_errors:
                for tf, error in loading_errors.items():
                    logger.warning(f"Failed to load {tf}: {error}")

            logger.info(
                f"Successfully loaded and synchronized {len(aligned_data)} timeframes for {symbol}"
            )

            return aligned_data

        except Exception as e:
            error_msg = f"Failed to synchronize timeframes: {str(e)}"
            logger.error(error_msg)
            raise DataError(
                f"Multi-timeframe synchronization failed for {symbol}",
                error_code="MULTI_TF_SYNC_FAILED",
                details={
                    "symbol": symbol,
                    "timeframes": list(timeframe_data.keys()),
                    "base_timeframe": base_timeframe,
                    "error": str(e),
                },
            ) from e

    def _find_common_data_coverage(
        self, timeframe_data: dict[str, pd.DataFrame], symbol: str
    ) -> dict[str, Any]:
        """
        Find the common data coverage intersection across all timeframes.

        This method analyzes the date ranges of all loaded timeframes and identifies
        the largest common time window where all timeframes have data. It also
        validates that this window is sufficient for meaningful training.

        Args:
            timeframe_data: Dictionary mapping timeframes to DataFrames
            symbol: Trading symbol (for logging/error context)

        Returns:
            Dictionary with coverage analysis results:
            {
                'start_date': pd.Timestamp,     # Common coverage start
                'end_date': pd.Timestamp,       # Common coverage end
                'days': int,                    # Number of days in common window
                'min_bars': int,                # Minimum bars across all timeframes in window
                'max_bars': int,                # Maximum bars across all timeframes in window
                'is_sufficient': bool,          # Whether coverage is sufficient for training
                'timeframe_details': Dict       # Per-timeframe coverage details
            }
        """
        if len(timeframe_data) < 2:
            # Single timeframe case - no intersection needed
            tf, df = next(iter(timeframe_data.items()))
            return {
                "start_date": df.index[0],
                "end_date": df.index[-1],
                "days": (df.index[-1] - df.index[0]).days,
                "min_bars": len(df),
                "max_bars": len(df),
                "is_sufficient": len(df) >= 50,  # Minimum for MACD + training
                "timeframe_details": {
                    tf: {"bars": len(df), "start": df.index[0], "end": df.index[-1]}
                },
            }

        # Multi-timeframe case - find intersection
        timeframe_ranges = {}

        for tf, df in timeframe_data.items():
            if df.empty:
                logger.warning(
                    f"Empty DataFrame for timeframe {tf}, skipping from coverage analysis"
                )
                continue

            timeframe_ranges[tf] = {
                "start": df.index[0],
                "end": df.index[-1],
                "bars": len(df),
                "df": df,
            }

        if not timeframe_ranges:
            return {
                "start_date": None,
                "end_date": None,
                "days": 0,
                "min_bars": 0,
                "max_bars": 0,
                "is_sufficient": False,
                "timeframe_details": {},
            }

        # Find the intersection: latest start date and earliest end date
        common_start = max(info["start"] for info in timeframe_ranges.values())
        common_end = min(info["end"] for info in timeframe_ranges.values())

        # Validate that we have a positive time window
        if common_start >= common_end:
            logger.warning(
                f"No temporal overlap found between timeframes for {symbol}. "
                f"Start: {common_start}, End: {common_end}"
            )
            return {
                "start_date": common_start,
                "end_date": common_end,
                "days": 0,
                "min_bars": 0,
                "max_bars": 0,
                "is_sufficient": False,
                "timeframe_details": timeframe_ranges,
            }

        # Calculate how many bars each timeframe has in the common window
        common_window_bars = {}
        for tf, info in timeframe_ranges.items():
            # Slice DataFrame to common window
            common_slice = info["df"].loc[common_start:common_end]
            common_window_bars[tf] = len(common_slice)

        min_bars = min(common_window_bars.values()) if common_window_bars else 0
        max_bars = max(common_window_bars.values()) if common_window_bars else 0
        days = (common_end - common_start).days

        # Determine if coverage is sufficient
        # Need at least 50 bars for MACD calculation (26+9=35) plus some training data
        is_sufficient = min_bars >= 50 and days >= 7  # At least 1 week and 50 bars

        logger.debug(
            f"Common coverage analysis for {symbol}: "
            f"{common_start.strftime('%Y-%m-%d')} to {common_end.strftime('%Y-%m-%d')} "
            f"({days} days, {min_bars}-{max_bars} bars)"
        )

        return {
            "start_date": common_start,
            "end_date": common_end,
            "days": days,
            "min_bars": min_bars,
            "max_bars": max_bars,
            "is_sufficient": is_sufficient,
            "timeframe_details": {
                tf: {
                    "original_bars": info["bars"],
                    "common_bars": common_window_bars.get(tf, 0),
                    "original_start": info["start"],
                    "original_end": info["end"],
                }
                for tf, info in timeframe_ranges.items()
            },
        }
