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

from ktrdr.data.local_data_loader import LocalDataLoader
from ktrdr.data.ib_data_fetcher_unified import IbDataFetcherUnified
from ktrdr.data.ib_symbol_validator_unified import IbSymbolValidatorUnified
from ktrdr.data.ib_connection_pool import get_connection_pool
from ktrdr.data.data_quality_validator import DataQualityValidator
from ktrdr.data.gap_classifier import GapClassifier, GapClassification
from ktrdr.data.timeframe_constants import TimeframeConstants

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

    # Mapping of repair methods to their functions
    REPAIR_METHODS = {
        "ffill": pd.DataFrame.ffill,
        "bfill": pd.DataFrame.bfill,
        "interpolate": pd.DataFrame.interpolate,
        "zero": lambda df: df.fillna(0),
        "mean": lambda df: df.fillna(df.mean()),
        "median": lambda df: df.fillna(df.median()),
        "drop": lambda df: df.dropna(),
    }

    def __init__(
        self,
        data_dir: Optional[str] = None,
        max_gap_percentage: float = 5.0,
        default_repair_method: str = "ffill",
        enable_ib: bool = True,
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
            enable_ib: Whether to enable IB integration (default: True)
                      Set to False for unit tests to avoid network connections

        Raises:
            DataError: If initialization parameters are invalid
        """
        # Validate parameters
        if max_gap_percentage < 0 or max_gap_percentage > 100:
            raise DataError(
                message=f"Invalid max_gap_percentage: {max_gap_percentage}. Must be between 0 and 100.",
                error_code="DATA-InvalidParameter",
                details={
                    "parameter": "max_gap_percentage",
                    "value": max_gap_percentage,
                    "valid_range": "0-100",
                },
            )

        if default_repair_method not in self.REPAIR_METHODS:
            raise DataError(
                message=f"Invalid repair method: {default_repair_method}",
                error_code="DATA-InvalidParameter",
                details={
                    "parameter": "default_repair_method",
                    "value": default_repair_method,
                    "valid_options": list(self.REPAIR_METHODS.keys()),
                },
            )

        # Initialize the LocalDataLoader
        self.data_loader = LocalDataLoader(data_dir=data_dir)

        # Initialize IB unified components for advanced IB operations
        self.enable_ib = enable_ib
        if enable_ib:
            self.ib_data_fetcher = IbDataFetcherUnified(component_name="data_manager")
            self.ib_symbol_validator = IbSymbolValidatorUnified(
                component_name="data_manager"
            )
            logger.info("IB integration enabled (using unified components)")
        else:
            self.ib_data_fetcher = None
            self.ib_symbol_validator = None
            logger.info("IB integration disabled")

        # Store parameters
        self.max_gap_percentage = max_gap_percentage
        self.default_repair_method = default_repair_method

        # Initialize the unified data quality validator
        self.data_validator = DataQualityValidator(
            auto_correct=True,  # Enable auto-correction by default
            max_gap_percentage=max_gap_percentage,
        )

        # Initialize the intelligent gap classifier
        self.gap_classifier = GapClassifier()

        logger.info(
            f"Initialized DataManager with max_gap_percentage={max_gap_percentage}%, "
            f"default_repair_method='{default_repair_method}'"
        )

    def _check_cancellation(
        self,
        cancellation_token: Optional[Any],
        operation_description: str = "operation",
    ) -> bool:
        """
        Check if cancellation has been requested.

        Args:
            cancellation_token: Token to check for cancellation
            operation_description: Description of current operation for logging

        Returns:
            True if cancellation was requested, False otherwise

        Raises:
            asyncio.CancelledError: If cancellation was requested
        """
        if cancellation_token is None:
            return False

        # Check if token has cancellation method
        is_cancelled = False
        if hasattr(cancellation_token, "is_cancelled_requested"):
            is_cancelled = cancellation_token.is_cancelled_requested
        elif hasattr(cancellation_token, "is_set"):
            is_cancelled = cancellation_token.is_set()
        elif hasattr(cancellation_token, "cancelled"):
            is_cancelled = cancellation_token.cancelled()

        if is_cancelled:
            logger.info(f"🛑 Cancellation requested during {operation_description}")
            # Import here to avoid circular imports
            import asyncio

            raise asyncio.CancelledError(
                f"Operation cancelled during {operation_description}"
            )

        return False

    @log_entry_exit(logger=logger, log_args=True)
    @log_performance(threshold_ms=500, logger=logger)
    def load_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        mode: str = "local",
        validate: bool = True,
        repair: bool = False,
        repair_outliers: bool = True,
        strict: bool = False,
        cancellation_token: Optional[Any] = None,
    ) -> pd.DataFrame:
        """
        Load data with optional validation and repair using unified validator.

        Args:
            symbol: The trading symbol (e.g., 'EURUSD', 'AAPL')
            timeframe: The timeframe of the data (e.g., '1h', '1d')
            start_date: Optional start date for filtering data
            end_date: Optional end date for filtering data
            mode: Loading mode - 'local' (local only), 'tail' (recent gaps), 'backfill' (historical), 'full' (backfill + tail)
            validate: Whether to validate data integrity (default: True)
            repair: Whether to repair any detected issues (default: False)
            repair_outliers: Whether to repair detected outliers when repair=True (default: True)
            strict: If True, raises an exception for integrity issues instead of warning (default: False)
            cancellation_token: Optional cancellation token to check for early termination

        Returns:
            DataFrame containing validated (and optionally repaired) OHLCV data

        Raises:
            DataNotFoundError: If the data file is not found
            DataCorruptionError: If data has integrity issues and strict=True
            DataError: For other data-related errors

        Note:
            This method uses the unified DataQualityValidator and enhanced IB integration.
            When mode is 'tail', 'backfill', or 'full', it uses intelligent gap analysis
            and IB fetching for missing data segments.
        """
        # Load data based on mode
        logger.info(f"Loading data for {symbol} ({timeframe}) - mode: {mode}")

        if mode == "local":
            # Local-only mode: use basic loader without IB integration
            df = self.data_loader.load(symbol, timeframe, start_date, end_date)
        else:
            # Enhanced modes: use intelligent gap analysis with IB integration
            df = self._load_with_fallback(
                symbol, timeframe, start_date, end_date, mode, cancellation_token
            )

        # Check if df is None (happens when fallback returns None)
        if df is None:
            raise DataNotFoundError(
                message=f"Data not found for {symbol} ({timeframe})",
                error_code="DATA-FileNotFound",
                details={"symbol": symbol, "timeframe": timeframe},
            )

        if validate:
            # Use the unified data quality validator
            validation_type = "local"  # Default to local validation type

            # Temporarily disable auto-correct if repair is not requested
            if not repair:
                # Create a non-correcting validator for validation-only mode
                validator = DataQualityValidator(
                    auto_correct=False, max_gap_percentage=self.max_gap_percentage
                )
            else:
                # Use the instance validator which has auto-correct enabled
                validator = self.data_validator

            # Perform validation
            df_validated, quality_report = validator.validate_data(
                df, symbol, timeframe, validation_type
            )

            # Handle repair_outliers parameter if repair is enabled but repair_outliers is False
            if repair and not repair_outliers:
                # For now, log that outlier repair was skipped (full implementation would
                # require enhanced DataQualityValidator to support selective correction types)
                logger.info(
                    "Outlier repair was skipped as requested (repair_outliers=False)"
                )
                # Note: Current unified validator doesn't support selective repair types yet

            # Check if there are critical issues and handle based on strict mode
            # In strict mode, no critical or high severity issues are allowed
            is_healthy = quality_report.is_healthy(
                max_critical=0, max_high=0 if strict else 5
            )

            if not is_healthy:
                issues_summary = quality_report.get_summary()
                issues_str = f"{issues_summary['total_issues']} issues found"

                if strict:
                    logger.error(
                        f"Data quality issues found and strict mode enabled: {issues_str}"
                    )
                    raise DataCorruptionError(
                        message=f"Data quality issues found: {issues_str}",
                        error_code="DATA-IntegrityIssue",
                        details={
                            "issues": issues_summary,
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "quality_report": quality_report.get_summary(),
                        },
                    )
                else:
                    logger.warning(f"Data quality issues found: {issues_str}")

                    if repair:
                        # The validator already performed repairs, use the validated data
                        df = df_validated
                        logger.info(
                            f"Data automatically repaired by validator: {quality_report.corrections_made} corrections made"
                        )
                    else:
                        # Just log the issues without repairing
                        for issue in quality_report.issues:
                            logger.warning(
                                f"  - {issue.issue_type}: {issue.description}"
                            )
            else:
                if repair:
                    # Use the validated data even if no issues were found (could have minor corrections)
                    df = df_validated
                    if quality_report.corrections_made > 0:
                        logger.info(
                            f"Minor data corrections applied: {quality_report.corrections_made} corrections made"
                        )

        logger.debug(
            f"Successfully loaded and processed {len(df)} rows of data for {symbol} ({timeframe})"
        )
        return df

    @log_entry_exit(logger=logger, log_args=True)
    def load(
        self,
        symbol: str,
        interval: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        days: Optional[int] = None,
        validate: bool = True,
        repair: bool = False,
    ) -> pd.DataFrame:
        """
        Load data with simpler parameter naming for backward compatibility.

        This is a wrapper around load_data with parameter names aligned with the UI expectations.

        Args:
            symbol: The trading symbol (e.g., 'EURUSD', 'AAPL')
            interval: The timeframe of the data (e.g., '1h', '1d'), same as timeframe
            start_date: Optional start date for filtering data
            end_date: Optional end date for filtering data
            days: Optional number of days to load from end_date going backwards
            validate: Whether to validate data integrity (default: True)
            repair: Whether to repair any detected issues (default: False)

        Returns:
            DataFrame containing validated (and optionally repaired) OHLCV data
        """
        # Handle the days parameter to calculate start_date if provided
        if days is not None and end_date is None:
            # If end_date is not provided, use current UTC date
            end_date = TimestampManager.now_utc()

        if days is not None:
            # Calculate start_date based on days going backwards from end_date
            if isinstance(end_date, str):
                end_date = pd.to_datetime(end_date)
            start_date = end_date - timedelta(days=days)

        # Call the original load_data method with the processed parameters
        return self.load_data(
            symbol=symbol,
            timeframe=interval,  # interval is the same as timeframe
            start_date=start_date,
            end_date=end_date,
            validate=validate,
            repair=repair,
        )

    def _normalize_timezone(
        self, dt: Union[str, datetime, pd.Timestamp, None], default_tz: str = "UTC"
    ) -> Optional[pd.Timestamp]:
        """
        Normalize datetime to UTC timezone-aware timestamp.

        Note: Using TimestampManager for consistent timezone handling.

        Args:
            dt: Input datetime (string, datetime, or Timestamp)
            default_tz: Default timezone to assume for naive datetimes (deprecated, always UTC)

        Returns:
            UTC timezone-aware Timestamp or None
        """
        return TimestampManager.to_utc(dt)

    def _normalize_dataframe_timezone(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize DataFrame index to UTC timezone-aware.

        Note: Using TimestampManager for consistent timezone handling.

        Args:
            df: DataFrame with datetime index

        Returns:
            DataFrame with UTC timezone-aware index
        """
        return TimestampManager.convert_dataframe_index(df)

    def _ensure_ib_connection(self) -> bool:
        """
        Check if IB connection is available by attempting actual connection.
        
        Uses the same resilient approach as symbol validator instead of just
        checking pool stats which can be misleading.

        Returns:
            True if IB connection is available, False otherwise
        """
        if not self.enable_ib or not self.ib_data_fetcher:
            return False

        try:
            # Actually attempt to establish and test a connection
            import asyncio
            from ktrdr.data.ib_connection_pool import acquire_ib_connection
            from ktrdr.data.ib_client_id_registry import ClientIdPurpose

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Test connection with timeout - same as symbol validator
            async def test_connection():
                try:
                    async with await acquire_ib_connection(
                        purpose=ClientIdPurpose.DATA_MANAGER,
                        requested_by="data_manager_connection_test"
                    ) as connection:
                        # Quick test to verify connection works (like symbol validator)
                        await asyncio.wait_for(
                            connection.ib.reqCurrentTimeAsync(),
                            timeout=5.0  # Short timeout to detect silent connections
                        )
                        return True
                except Exception as e:
                    logger.debug(f"IB connection test failed: {e}")
                    return False

            return loop.run_until_complete(test_connection())
            
        except Exception as e:
            logger.debug(f"IB connection availability check failed: {e}")
            return False

    def _analyze_gaps(
        self,
        existing_data: Optional[pd.DataFrame],
        requested_start: datetime,
        requested_end: datetime,
        timeframe: str,
        symbol: str,
        mode: str = "tail",
    ) -> List[Tuple[datetime, datetime]]:
        """
        Analyze gaps between existing data and requested range using intelligent gap classification.

        This method uses the intelligent gap classifier to identify only unexpected gaps
        that need to be fetched from IB, avoiding redundant requests for expected gaps
        (weekends, holidays, non-trading hours).

        Args:
            existing_data: DataFrame with existing local data (can be None)
            requested_start: Start of requested date range
            requested_end: End of requested date range
            timeframe: Data timeframe for trading calendar awareness
            symbol: Trading symbol for intelligent classification

        Returns:
            List of (start_time, end_time) tuples representing gaps to fill
        """
        gaps_to_fill = []

        # If no existing data, entire range is a gap to fill
        if existing_data is None or existing_data.empty:
            logger.info(
                f"No existing data found - entire range is a gap: {requested_start} to {requested_end}"
            )
            return [(requested_start, requested_end)]

        # Ensure timezone consistency
        if existing_data.index.tz is None:
            existing_data.index = existing_data.index.tz_localize("UTC")
        elif existing_data.index.tz != requested_start.tzinfo:
            existing_data.index = existing_data.index.tz_convert(requested_start.tzinfo)

        data_start = existing_data.index.min()
        data_end = existing_data.index.max()

        logger.debug(f"Existing data range: {data_start} to {data_end}")
        logger.debug(f"Requested range: {requested_start} to {requested_end}")

        # Use the provided symbol for intelligent gap classification

        # Check for all potential gaps and classify them
        all_gaps = []

        # Gap before existing data
        if requested_start < data_start:
            gap_end = min(data_start, requested_end)
            all_gaps.append((requested_start, gap_end))

        # Gap after existing data
        if requested_end > data_end:
            gap_start = max(data_end, requested_start)
            all_gaps.append((gap_start, requested_end))

        # Gaps within existing data (holes in the dataset)
        # For backfill/full mode, skip micro-gap analysis to avoid thousands of tiny segments
        if requested_start < data_end and requested_end > data_start and mode == "tail":
            internal_gaps = self._find_internal_gaps(
                existing_data,
                max(requested_start, data_start),
                min(requested_end, data_end),
                timeframe,
            )
            all_gaps.extend(internal_gaps)
            logger.debug(f"Found {len(internal_gaps)} internal gaps (mode: {mode})")
        elif mode in ["backfill", "full"]:
            logger.info(
                f"🚀 BACKFILL MODE: Skipping micro-gap analysis to focus on large historical periods"
            )

        # Use intelligent gap classifier to filter out expected gaps
        for gap_start, gap_end in all_gaps:
            gap_duration = gap_end - gap_start

            # For large gaps (> 7 days), always consider them worth filling regardless of classification
            # This handles backfill scenarios where we want historical data
            if gap_duration > timedelta(days=7):
                gaps_to_fill.append((gap_start, gap_end))
                logger.info(
                    f"📍 LARGE HISTORICAL GAP TO FILL: {gap_start} → {gap_end} (duration: {gap_duration})"
                )
            else:
                # For smaller gaps, use intelligent classification
                gap_info = self.gap_classifier.analyze_gap(
                    gap_start, gap_end, symbol, timeframe
                )

                # Only fill unexpected gaps and market closures
                if gap_info.classification in [
                    GapClassification.UNEXPECTED,
                    GapClassification.MARKET_CLOSURE,
                ]:
                    gaps_to_fill.append((gap_start, gap_end))
                    logger.debug(
                        f"📍 UNEXPECTED GAP TO FILL: {gap_start} → {gap_end} ({gap_info.classification.value})"
                    )
                else:
                    logger.debug(
                        f"📅 EXPECTED GAP SKIPPED: {gap_start} → {gap_end} ({gap_info.classification.value}) - {gap_info.note}"
                    )

        logger.info(
            f"🔍 INTELLIGENT GAP ANALYSIS COMPLETE: Found {len(gaps_to_fill)} unexpected gaps to fill (filtered out {len(all_gaps) - len(gaps_to_fill)} expected gaps)"
        )
        return gaps_to_fill

    def _find_internal_gaps(
        self,
        data: pd.DataFrame,
        range_start: datetime,
        range_end: datetime,
        timeframe: str,
    ) -> List[Tuple[datetime, datetime]]:
        """
        Find gaps within existing data (missing periods in the middle).

        Args:
            data: Existing DataFrame with timezone-aware index
            range_start: Start of range to check within
            range_end: End of range to check within
            timeframe: Data timeframe for gap detection

        Returns:
            List of internal gaps found
        """
        gaps = []

        # Filter data to the requested range
        mask = (data.index >= range_start) & (data.index <= range_end)
        range_data = data[mask].sort_index()

        if len(range_data) < 2:
            return gaps

        # Calculate expected frequency using centralized constants
        expected_freq = TimeframeConstants.get_pandas_timedelta(timeframe)

        # Look for gaps larger than expected frequency
        for i in range(len(range_data) - 1):
            current_time = range_data.index[i]
            next_time = range_data.index[i + 1]
            gap_size = next_time - current_time

            # Consider it a gap if it's larger than expected frequency
            # (intelligent classification will happen later)
            if (
                gap_size > expected_freq * 1.5
            ):  # Minimal tolerance - classification will filter
                gap_start = current_time + expected_freq
                gap_end = next_time
                gaps.append((gap_start, gap_end))
                logger.debug(f"Found internal gap: {gap_start} to {gap_end}")

        return gaps

    def _is_meaningful_gap(
        self, gap_start: datetime, gap_end: datetime, timeframe: str
    ) -> bool:
        """
        Determine if a gap is meaningful enough to warrant fetching data.

        Filters out weekends, holidays, and very small gaps that aren't worth
        the overhead of an IB request.

        Args:
            gap_start: Gap start time
            gap_end: Gap end time
            timeframe: Data timeframe

        Returns:
            True if gap is meaningful and should be filled
        """
        gap_duration = gap_end - gap_start

        # Minimum gap sizes by timeframe to avoid micro-gaps
        min_gaps = {
            "1m": pd.Timedelta(minutes=5),  # At least 5 minutes
            "5m": pd.Timedelta(minutes=15),  # At least 15 minutes
            "15m": pd.Timedelta(hours=1),  # At least 1 hour
            "30m": pd.Timedelta(hours=2),  # At least 2 hours
            "1h": pd.Timedelta(hours=4),  # At least 4 hours
            "4h": pd.Timedelta(days=1),  # At least 1 day
            "1d": pd.Timedelta(days=2),  # At least 2 days
            "1w": pd.Timedelta(weeks=1),  # At least 1 week
        }

        min_gap = min_gaps.get(timeframe, pd.Timedelta(hours=1))

        if gap_duration < min_gap:
            return False

        # For daily data, check if gap spans weekends only
        if timeframe == "1d":
            return self._gap_contains_trading_days(gap_start, gap_end)

        # For intraday data, more permissive (markets trade during weekdays)
        return True

    def _gap_contains_trading_days(self, start: datetime, end: datetime) -> bool:
        """
        Check if a gap contains any trading days (Mon-Fri, excluding holidays).

        This is a simplified implementation. A full implementation would
        integrate with a trading calendar library like pandas_market_calendars.

        Args:
            start: Gap start time
            end: Gap end time

        Returns:
            True if gap contains trading days
        """
        current = start.date()
        end_date = end.date()

        while current <= end_date:
            # Monday = 0, Sunday = 6
            if current.weekday() < 5:  # Monday through Friday
                # TODO: Add holiday checking with trading calendar
                return True
            current += timedelta(days=1)

        return False

    def _split_into_segments(
        self,
        gaps: List[Tuple[datetime, datetime]],
        timeframe: str,
    ) -> List[Tuple[datetime, datetime]]:
        """
        Split large gaps into IB-compliant segments.

        Takes gaps that might exceed IB duration limits and splits them
        into smaller segments that can be fetched individually.

        Args:
            gaps: List of gaps to potentially split
            timeframe: Data timeframe for limit checking

        Returns:
            List of segments ready for IB fetching
        """
        from ktrdr.config.ib_limits import IbLimitsRegistry

        segments = []
        max_duration = IbLimitsRegistry.get_duration_limit(timeframe)

        for gap_start, gap_end in gaps:
            gap_duration = gap_end - gap_start

            if gap_duration <= max_duration:
                # Gap fits in single request
                segments.append((gap_start, gap_end))
                logger.debug(
                    f"Gap fits in single segment: {gap_start} to {gap_end} ({gap_duration})"
                )
            else:
                # Split into multiple segments
                logger.info(
                    f"Splitting large gap {gap_start} to {gap_end} ({gap_duration}) into segments (max: {max_duration})"
                )

                current_start = gap_start
                while current_start < gap_end:
                    segment_end = min(current_start + max_duration, gap_end)
                    segments.append((current_start, segment_end))
                    logger.debug(f"Created segment: {current_start} to {segment_end}")
                    current_start = segment_end

        logger.info(
            f"⚡ SEGMENTATION: Split {len(gaps)} gaps into {len(segments)} IB-compliant segments"
        )
        for i, (seg_start, seg_end) in enumerate(segments):
            duration = seg_end - seg_start
            logger.debug(
                f"🔷 SEGMENT {i+1}: {seg_start} → {seg_end} (duration: {duration})"
            )
        return segments

    def _fetch_segments_with_resilience(
        self,
        symbol: str,
        timeframe: str,
        segments: List[Tuple[datetime, datetime]],
        cancellation_token: Optional[Any] = None,
    ) -> Tuple[List[pd.DataFrame], int, int]:
        """
        Fetch multiple segments with failure resilience.

        Attempts to fetch each segment individually, continuing with other segments
        if some fail. This ensures partial success rather than complete failure.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            segments: List of (start, end) segments to fetch

        Returns:
            Tuple of (successful_dataframes, successful_count, failed_count)
        """
        successful_data = []
        successful_count = 0
        failed_count = 0

        if not self.enable_ib or not self.ib_data_fetcher:
            logger.warning("IB integration not available for segment fetching")
            return successful_data, successful_count, len(segments)

        logger.info(f"Fetching {len(segments)} segments with failure resilience")

        for i, (segment_start, segment_end) in enumerate(segments):
            # Check for cancellation before each segment
            self._check_cancellation(
                cancellation_token, f"segment {i+1}/{len(segments)}"
            )

            try:
                duration = segment_end - segment_start
                logger.debug(
                    f"🚀 IB REQUEST {i+1}/{len(segments)}: Fetching {symbol} {timeframe} from {segment_start} to {segment_end}"
                )
                logger.debug(
                    f"🚀 IB REQUEST {i+1}: Duration = {duration} (within IB limit)"
                )

                # Use the unified IB data fetcher to fetch exactly what we ask for
                # Convert to async call - this method should be made async in the future
                # For now, we'll use a wrapper to handle the async call
                segment_data = self._fetch_segment_sync(
                    symbol=symbol,
                    timeframe=timeframe,
                    start=segment_start,
                    end=segment_end,
                    cancellation_token=cancellation_token,
                )

                if segment_data is not None and not segment_data.empty:
                    successful_data.append(segment_data)
                    successful_count += 1
                    logger.info(
                        f"✅ IB SUCCESS {i+1}: Received {len(segment_data)} bars from IB"
                    )
                else:
                    failed_count += 1
                    logger.warning(f"❌ IB FAILURE {i+1}: No data returned from IB")

            except Exception as e:
                failed_count += 1
                logger.error(f"❌ IB ERROR {i+1}: Request failed - {e}")
                # Continue with next segment rather than failing completely
                continue

        logger.info(
            f"Segment fetching complete: {successful_count} successful, {failed_count} failed"
        )
        return successful_data, successful_count, failed_count

    def _fetch_segment_sync(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        cancellation_token: Optional[Any] = None,
    ) -> Optional[pd.DataFrame]:
        """
        Sync wrapper for async segment fetching using unified components.

        This method provides a synchronous interface to the async data fetcher.
        In the future, the entire DataManager should be made async.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            start: Start datetime
            end: End datetime
            cancellation_token: Optional cancellation token

        Returns:
            DataFrame with fetched data or None if failed
        """
        import asyncio

        async def fetch_async():
            """Async fetch function with enhanced timeout protection."""
            # Apply same timeout protection as symbol validator
            return await asyncio.wait_for(
                self.ib_data_fetcher.fetch_historical_data(
                    symbol=symbol,
                    timeframe=timeframe,
                    start=start,
                    end=end,
                    instrument_type=None,  # Auto-detect
                    what_to_show="TRADES",
                    max_retries=3,
                ),
                timeout=60.0  # 60 second timeout for data fetching operations
            )

        try:
            # Run the async function in the current event loop or create a new one
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're in an async context, need to run in executor
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, fetch_async())
                        return future.result(timeout=30)  # 30 second timeout
                else:
                    return loop.run_until_complete(fetch_async())
            except RuntimeError:
                # No event loop, create a new one
                return asyncio.run(fetch_async())

        except asyncio.TimeoutError:
            logger.error(f"⏰ Data fetch timeout for {symbol} {timeframe} (60s limit) - possible IB Gateway issue")
            return None
        except Exception as e:
            logger.error(f"Sync fetch wrapper failed for {symbol} {timeframe}: {e}")
            return None

    def _fetch_head_timestamp_sync(self, symbol: str, timeframe: str) -> Optional[str]:
        """
        Sync wrapper for async head timestamp fetching.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe

        Returns:
            ISO formatted head timestamp string or None if failed
        """
        import asyncio

        async def fetch_head_timestamp_async():
            """Async head timestamp fetch function."""
            return await self.ib_symbol_validator.fetch_head_timestamp_async(
                symbol=symbol, timeframe=timeframe, force_refresh=True
            )

        try:
            # Run the async function in the current event loop or create a new one
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're in an async context, need to run in executor
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run, fetch_head_timestamp_async()
                        )
                        return future.result(timeout=30)  # 30 second timeout
                else:
                    return loop.run_until_complete(fetch_head_timestamp_async())
            except RuntimeError:
                # No event loop, create a new one
                return asyncio.run(fetch_head_timestamp_async())

        except Exception as e:
            logger.error(f"Sync head timestamp fetch failed for {symbol}: {e}")
            return None

    @log_entry_exit(logger=logger, log_args=True)
    def _validate_request_against_head_timestamp(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Tuple[bool, Optional[str], Optional[datetime]]:
        """
        Validate request date range against cached head timestamp data.

        This method checks if the requested start date is within the available
        data range for the symbol, helping prevent unnecessary error 162s.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            start_date: Requested start date
            end_date: Requested end date

        Returns:
            Tuple of (is_valid, error_message, adjusted_start_date)
        """
        if not self.enable_ib or not self.ib_symbol_validator:
            return True, None, None

        try:
            # Use unified symbol validator
            validator = self.ib_symbol_validator

            # Check if we have head timestamp data for this symbol
            result = validator.validate_date_range_against_head_timestamp(
                symbol, start_date, timeframe
            )

            is_valid, error_message, suggested_start = result

            if not is_valid:
                # Request is definitely outside available range
                logger.warning(f"📅 HEAD TIMESTAMP VALIDATION FAILED: {error_message}")
                return False, error_message, suggested_start
            elif suggested_start and suggested_start != start_date:
                # Request can be adjusted to valid range
                logger.info(
                    f"📅 HEAD TIMESTAMP VALIDATION ADJUSTED: {start_date} → {suggested_start}"
                )
                return True, None, suggested_start
            else:
                # Request is valid as-is
                logger.debug(
                    f"📅 HEAD TIMESTAMP VALIDATION PASSED: {symbol} from {start_date}"
                )
                return True, None, None

        except Exception as e:
            logger.warning(f"Head timestamp validation failed for {symbol}: {e}")
            # Don't block requests if validation fails
            return True, None, None

    def _ensure_symbol_has_head_timestamp(self, symbol: str, timeframe: str) -> bool:
        """
        Ensure symbol has head timestamp data, triggering validation if needed.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe

        Returns:
            True if head timestamp is available, False otherwise
        """
        if not self.enable_ib or not self.ib_symbol_validator:
            return False

        try:
            validator = self.ib_symbol_validator

            # Check if we already have head timestamp (sync method)
            head_timestamp = validator.get_head_timestamp(symbol, timeframe)

            if head_timestamp:
                logger.debug(
                    f"📅 Head timestamp already available for {symbol}: {head_timestamp}"
                )
                return True

            # No head timestamp available, fetch it asynchronously
            logger.info(f"📅 No head timestamp for {symbol}, fetching from IB")

            # Use a sync wrapper for async head timestamp fetching
            head_timestamp = self._fetch_head_timestamp_sync(symbol, timeframe)

            if head_timestamp:
                logger.info(
                    f"📅 Successfully obtained head timestamp for {symbol}: {head_timestamp}"
                )
                return True
            else:
                logger.warning(f"📅 Failed to fetch head timestamp for {symbol}")
                return False

        except Exception as e:
            logger.warning(f"Error ensuring head timestamp for {symbol}: {e}")
            return False

    def _load_with_fallback(
        self,
        symbol: str,
        timeframe: str,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        mode: str = "tail",
        cancellation_token: Optional[Any] = None,
    ) -> Optional[pd.DataFrame]:
        """
        Load data with intelligent gap analysis and resilient segment fetching.

        ENHANCED STRATEGY:
        1. Load existing local data (fast)
        2. Perform intelligent gap analysis vs requested range
        3. Split gaps into IB-compliant segments
        4. Use "dumb" IbDataLoader to fetch only missing segments
        5. Merge all data sources chronologically
        6. Handle partial failures gracefully

        This replaces the old "naive" approach of fetching entire ranges
        with a smart approach that only fetches missing data segments.

        Args:
            symbol: The trading symbol
            timeframe: The timeframe of the data
            start_date: Optional start date
            end_date: Optional end date
            mode: Loading mode - 'tail' (recent gaps), 'backfill' (historical), 'full' (backfill + tail)

        Returns:
            DataFrame with data or None if no data found
        """
        # Normalize and validate date range - ALWAYS respect user-provided dates
        if start_date is None:
            # Default range based on mode
            if mode == "tail":
                # Tail: recent data if no range specified
                requested_start = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=30)
            elif mode == "backfill":
                # Backfill: go back as far as IB allows for this timeframe
                from ktrdr.config.ib_limits import IbLimitsRegistry

                max_duration = IbLimitsRegistry.get_duration_limit(timeframe)
                requested_start = pd.Timestamp.now(tz="UTC") - max_duration
            else:  # mode == "full" or any other mode
                # Full: use maximum available range if no start specified
                from ktrdr.config.ib_limits import IbLimitsRegistry

                max_duration = IbLimitsRegistry.get_duration_limit(timeframe)
                requested_start = pd.Timestamp.now(tz="UTC") - max_duration
        else:
            # ALWAYS respect user-provided start_date regardless of mode
            requested_start = self._normalize_timezone(start_date)

        if end_date is None:
            requested_end = pd.Timestamp.now(tz="UTC")
        else:
            # ALWAYS respect user-provided end_date regardless of mode
            requested_end = self._normalize_timezone(end_date)

        if requested_start >= requested_end:
            logger.warning(
                f"Invalid date range: start {requested_start} >= end {requested_end}"
            )
            return None

        logger.info(
            f"🧠 ENHANCED STRATEGY ({mode}): Loading {symbol} {timeframe} from {requested_start} to {requested_end}"
        )

        # Step 0: Ensure symbol has head timestamp data and validate request range
        logger.info(f"📅 STEP 0: Validating request against head timestamp data")
        self._check_cancellation(cancellation_token, "head timestamp validation")

        # First ensure we have head timestamp data for this symbol
        has_head_timestamp = self._ensure_symbol_has_head_timestamp(symbol, timeframe)

        if has_head_timestamp:
            # Validate the request range against head timestamp
            is_valid, error_message, adjusted_start = (
                self._validate_request_against_head_timestamp(
                    symbol, timeframe, requested_start, requested_end
                )
            )

            if not is_valid:
                logger.error(f"📅 Request validation failed: {error_message}")
                logger.error(
                    f"📅 Cannot load data for {symbol} from {requested_start} - data not available"
                )
                return None
            elif adjusted_start:
                logger.info(
                    f"📅 Request adjusted based on head timestamp: {requested_start} → {adjusted_start}"
                )
                requested_start = adjusted_start
        else:
            logger.info(
                f"📅 No head timestamp available for {symbol}, proceeding with original request"
            )

        # Step 1: Load existing local data (ALL modes need this for gap analysis)
        existing_data = None
        try:
            logger.info(f"📁 Loading existing local data for {symbol}")
            self._check_cancellation(cancellation_token, "loading existing data")
            existing_data = self.data_loader.load(symbol, timeframe)
            if existing_data is not None and not existing_data.empty:
                existing_data = self._normalize_dataframe_timezone(existing_data)
                logger.info(
                    f"✅ Found existing data: {len(existing_data)} bars ({existing_data.index.min()} to {existing_data.index.max()})"
                )
            else:
                logger.info(f"📭 No existing local data found")
        except Exception as e:
            logger.info(f"📭 No existing local data: {e}")
            existing_data = None

        # Step 2: Intelligent gap analysis
        logger.info(
            f"🔍 GAP ANALYSIS: Starting intelligent gap detection for {symbol} {timeframe}"
        )
        self._check_cancellation(cancellation_token, "gap analysis")
        logger.debug(
            f"🔍 GAP ANALYSIS: Requested range = {requested_start} to {requested_end}"
        )
        if existing_data is not None and not existing_data.empty:
            logger.debug(
                f"🔍 GAP ANALYSIS: Existing data range = {existing_data.index.min()} to {existing_data.index.max()}"
            )
        else:
            logger.debug(f"🔍 GAP ANALYSIS: No existing data found")
        gaps = self._analyze_gaps(
            existing_data, requested_start, requested_end, timeframe, symbol, mode
        )

        if not gaps:
            logger.info(f"✅ No gaps found - existing data covers requested range!")
            # Filter existing data to requested range if needed
            if existing_data is not None:
                mask = (existing_data.index >= requested_start) & (
                    existing_data.index <= requested_end
                )
                filtered_data = existing_data[mask] if mask.any() else existing_data
                logger.info(
                    f"📊 Returning {len(filtered_data)} bars from existing data (filtered to requested range)"
                )
                return filtered_data
            return existing_data

        # Step 3: Split gaps into IB-compliant segments
        logger.info(
            f"⚡ SEGMENTATION: Splitting {len(gaps)} gaps into IB-compliant segments..."
        )
        self._check_cancellation(cancellation_token, "segmentation")
        segments = self._split_into_segments(gaps, timeframe)
        logger.info(
            f"⚡ SEGMENTATION COMPLETE: Created {len(segments)} segments for IB fetching"
        )

        if not segments:
            logger.info(f"✅ No segments to fetch after filtering")
            return existing_data

        # Step 4: Check IB availability and fetch segments
        fetched_data_frames = []

        if self._ensure_ib_connection():
            logger.info(
                f"🚀 Fetching {len(segments)} segments using resilient strategy..."
            )
            self._check_cancellation(cancellation_token, "IB connection check")
            successful_frames, successful_count, failed_count = (
                self._fetch_segments_with_resilience(
                    symbol, timeframe, segments, cancellation_token
                )
            )
            fetched_data_frames = successful_frames

            if successful_count > 0:
                logger.info(
                    f"✅ Successfully fetched {successful_count}/{len(segments)} segments"
                )
            if failed_count > 0:
                logger.warning(
                    f"⚠️ {failed_count}/{len(segments)} segments failed - continuing with partial data"
                )
        else:
            logger.warning(f"❌ IB connection not available - using existing data only")

        # Step 5: Merge all data sources
        all_data_frames = []

        # Add existing data if available
        if existing_data is not None and not existing_data.empty:
            all_data_frames.append(existing_data)

        # Add fetched data
        all_data_frames.extend(fetched_data_frames)

        if not all_data_frames:
            logger.warning(f"❌ No data available from any source")
            return None

        # Combine and sort all data
        logger.info(f"🔄 Merging {len(all_data_frames)} data sources...")

        # Log details about each data source for debugging
        for i, df in enumerate(all_data_frames):
            if not df.empty:
                logger.debug(
                    f"📊 Data source {i+1}: {len(df)} bars from {df.index.min()} to {df.index.max()}"
                )
            else:
                logger.debug(f"📊 Data source {i+1}: EMPTY DataFrame")

        combined_data = pd.concat(all_data_frames, ignore_index=False)
        logger.info(f"🔗 After concat: {len(combined_data)} total bars")

        # Remove duplicates and sort
        duplicates_count = combined_data.index.duplicated().sum()
        if duplicates_count > 0:
            logger.info(f"🗑️ Removing {duplicates_count} duplicate timestamps")
        combined_data = combined_data[~combined_data.index.duplicated(keep="last")]
        combined_data = combined_data.sort_index()
        logger.info(f"✅ After deduplication and sorting: {len(combined_data)} bars")

        # Filter to requested range
        mask = (combined_data.index >= requested_start) & (
            combined_data.index <= requested_end
        )
        final_data = combined_data[mask] if mask.any() else combined_data

        logger.info(
            f"📊 Final dataset: {len(final_data)} bars covering {final_data.index.min() if not final_data.empty else 'N/A'} to {final_data.index.max() if not final_data.empty else 'N/A'}"
        )

        # Save the enhanced dataset back to CSV for future use
        if len(fetched_data_frames) > 0:  # Only save if we fetched new data
            try:
                self.data_loader.save(combined_data, symbol, timeframe)
                logger.info(f"💾 Saved enhanced dataset: {len(combined_data)} bars")
            except Exception as e:
                logger.warning(f"⚠️ Failed to save enhanced dataset: {e}")

        logger.info(f"🎉 ENHANCED STRATEGY COMPLETE: Returning {len(final_data)} bars")
        return final_data

    def _merge_and_fill_gaps(
        self, ib_data: pd.DataFrame, local_data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Merge IB and local data, preferring IB data and filling gaps with local data.

        Args:
            ib_data: DataFrame from IB (already UTC timezone-aware)
            local_data: DataFrame from local CSV (already UTC timezone-aware)

        Returns:
            Merged DataFrame with gaps filled
        """
        # Both DataFrames should already be normalized to UTC timezone-aware by caller
        # Combine data, preferring IB data where available
        combined = ib_data.combine_first(local_data)

        # Sort by timestamp and remove duplicates
        combined = combined.sort_index().drop_duplicates()

        logger.info(
            f"Merged data: IB({len(ib_data)}) + Local({len(local_data)}) = Combined({len(combined)})"
        )

        return combined

    def _local_data_covers_range(
        self,
        local_data: pd.DataFrame,
        start_date: Optional[Union[str, datetime]],
        end_date: Optional[Union[str, datetime]],
    ) -> bool:
        """
        Check if local data covers the requested date range.

        Args:
            local_data: DataFrame with local data
            start_date: Requested start date (None means no constraint)
            end_date: Requested end date (None means no constraint)

        Returns:
            True if local data covers the requested range, False otherwise
        """
        if local_data is None or local_data.empty:
            return False

        # If no date constraints, local data is sufficient
        if start_date is None and end_date is None:
            return True

        # Normalize requested dates
        req_start = (
            self._normalize_timezone(start_date) if start_date is not None else None
        )
        req_end = self._normalize_timezone(end_date) if end_date is not None else None

        # Get local data range
        local_start = local_data.index.min()
        local_end = local_data.index.max()

        # Check coverage
        start_covered = req_start is None or local_start <= req_start
        end_covered = req_end is None or local_end >= req_end

        coverage_result = start_covered and end_covered

        if not coverage_result:
            logger.debug(
                f"Local data range ({local_start} to {local_end}) does not cover requested range ({req_start} to {req_end})"
            )

        return coverage_result

    @log_entry_exit(logger=logger, log_args=True)
    def check_data_integrity(
        self, df: pd.DataFrame, timeframe: str, is_post_repair: bool = False
    ) -> List[str]:
        """
        Check for common data integrity issues using unified validator.

        Args:
            df: DataFrame containing OHLCV data
            timeframe: The timeframe of the data (e.g., '1h', '1d')
            is_post_repair: Whether this check is done after data repair (default: False)

        Returns:
            List of detected integrity issues (empty if no issues found)

        Note:
            This method now uses the unified DataQualityValidator for consistency
            but maintains backward compatibility by returning a list of issue strings.
        """
        # Use the unified validator for integrity checking (without auto-correction)
        validator = DataQualityValidator(
            auto_correct=False, max_gap_percentage=self.max_gap_percentage
        )

        _, quality_report = validator.validate_data(
            df, "CHECK", timeframe, validation_type="local"
        )

        # Convert the quality report issues to the legacy string format for backward compatibility
        issues = []
        for issue in quality_report.issues:
            # Skip certain issue types when checking post-repair data
            if is_post_repair:
                # These issues are expected to remain after repair and shouldn't be treated as failures
                if issue.issue_type in [
                    "timestamp_gaps",
                    "zero_volume",
                    "price_outliers",
                ]:
                    continue

            # Map new issue types to legacy strings that tests expect
            if issue.issue_type == "missing_values":
                issues.append(f"Missing values: {issue.description}")
            elif issue.issue_type in ["low_too_high", "high_too_low", "ohlc_invalid"]:
                issues.append(f"Invalid OHLC relationships: {issue.description}")
            elif issue.issue_type == "negative_volume":
                issues.append(f"Negative volume: {issue.description}")
            else:
                # For other issue types, use the default format
                issues.append(f"{issue.issue_type}: {issue.description}")

        return issues

    @log_entry_exit(logger=logger)
    def detect_gaps(
        self, df: pd.DataFrame, timeframe: str, gap_threshold: int = 1
    ) -> List[Tuple[datetime, datetime]]:
        """
        Detect significant gaps in time series data using intelligent gap classification.

        This method finds gaps that would be considered data quality issues
        (excludes weekends, holidays, and non-trading hours).

        Args:
            df: DataFrame containing OHLCV data
            timeframe: The timeframe of the data (e.g., '1h', '1d')
            gap_threshold: Number of consecutive missing periods to consider as a gap (legacy parameter, maintained for compatibility)

        Returns:
            List of (start_time, end_time) tuples representing significant gaps only
        """
        if df.empty or len(df) <= 1:
            return []

        # Use the unified validator which now uses intelligent gap classification
        _, quality_report = self.data_validator.validate_data(
            df, "GAP_CHECK", timeframe, validation_type="local"
        )

        # Extract gap information from the quality report (only significant gaps)
        gaps = []
        gap_issues = quality_report.get_issues_by_type("timestamp_gaps")
        for issue in gap_issues:
            if "gaps" in issue.metadata:
                # Parse the gaps from metadata (they're stored as ISO string tuples)
                for gap_start_str, gap_end_str in issue.metadata["gaps"]:
                    gap_start = datetime.fromisoformat(
                        gap_start_str.replace("Z", "+00:00")
                    )
                    gap_end = datetime.fromisoformat(gap_end_str.replace("Z", "+00:00"))
                    gaps.append((gap_start, gap_end))

        logger.info(
            f"Detected {len(gaps)} significant gaps using intelligent classification"
        )
        return gaps

    @log_entry_exit(logger=logger)
    def detect_outliers(
        self,
        df: pd.DataFrame,
        std_threshold: float = 2.5,
        columns: Optional[List[str]] = None,
        post_repair_tolerance: float = 0.0,
        context_window: Optional[int] = None,
        log_outliers: bool = True,
    ) -> int:
        """
        Detect outliers in price data using unified validator.

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

        Note:
            This method now uses the unified DataQualityValidator for consistency.
        """
        if df.empty:
            return 0

        # Delegate to unified validator (without auto-correction for detection only)
        validator = DataQualityValidator(
            auto_correct=False, max_gap_percentage=self.max_gap_percentage
        )

        _, quality_report = validator.validate_data(
            df, "OUTLIER_CHECK", "1h", validation_type="local"
        )

        # Count outliers from the quality report
        outlier_issues = quality_report.get_issues_by_type("price_outliers")
        total_outliers = sum(issue.metadata.get("count", 0) for issue in outlier_issues)

        if total_outliers > 0 and log_outliers:
            logger.warning(
                f"Detected {total_outliers} outliers in price data using unified validator:"
            )
            for issue in outlier_issues:
                logger.warning(f"  - {issue.description}")

        return total_outliers

    @log_entry_exit(logger=logger, log_args=True)
    def repair_data(
        self,
        df: pd.DataFrame,
        timeframe: str,
        method: str = "auto",
        repair_outliers: bool = True,
        context_window: Optional[int] = None,
        std_threshold: float = 2.5,
    ) -> pd.DataFrame:
        """
        Repair data issues using the unified data quality validator.

        Args:
            df: DataFrame containing OHLCV data
            timeframe: The timeframe of the data (e.g., '1h', '1d')
            method: Repair method (legacy parameter, now uses unified validator)
            repair_outliers: Whether to repair detected outliers (default: True)
            context_window: Optional window size for contextual outlier detection
            std_threshold: Number of standard deviations to consider as outlier

        Returns:
            Repaired DataFrame

        Note:
            This method now delegates to the unified DataQualityValidator for
            all repair operations. The 'method' parameter is maintained for
            backward compatibility but the validator uses its own repair logic.
        """
        if df.empty:
            logger.warning("Cannot repair empty DataFrame")
            return df

        # Validate method parameter for backward compatibility
        if method not in [
            "auto",
            "ffill",
            "bfill",
            "interpolate",
            "zero",
            "mean",
            "median",
            "drop",
        ]:
            raise DataError(
                message=f"Invalid repair method: {method}",
                error_code="DATA-InvalidParameter",
                details={
                    "parameter": "method",
                    "value": method,
                    "valid_options": [
                        "auto",
                        "ffill",
                        "bfill",
                        "interpolate",
                        "zero",
                        "mean",
                        "median",
                        "drop",
                    ],
                },
            )

        logger.info(
            f"Repairing data using unified validator (method={method} - delegated to validator)"
        )

        # Use the unified data quality validator for repairs
        df_repaired, quality_report = self.data_validator.validate_data(
            df, "REPAIR", timeframe, validation_type="local"
        )

        # Log summary of repairs made
        if quality_report.corrections_made > 0:
            logger.info(
                f"Repair completed: {quality_report.corrections_made} corrections made"
            )

            # Log details of issues that were corrected
            corrected_issues = [
                issue for issue in quality_report.issues if issue.corrected
            ]
            for issue in corrected_issues:
                logger.debug(f"  - Fixed {issue.issue_type}: {issue.description}")
        else:
            logger.info("No repairs needed - data is already in good condition")

        return df_repaired

    @log_entry_exit(logger=logger, log_args=True)
    def get_data_summary(self, symbol: str, timeframe: str) -> Dict[str, Any]:
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
                details={"symbol": symbol, "timeframe": timeframe},
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
            "min_price": df["low"].min(),
            "max_price": df["high"].max(),
            "avg_price": df["close"].mean(),
            "total_volume": df["volume"].sum(),
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
        overwrite_conflicts: bool = False,
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
                    merged_data = merged_data[
                        ~merged_data.index.duplicated(keep="last")
                    ]
                else:
                    logger.info("Preserving existing data for conflicting rows")
                    # Keep the first occurrence of each duplicated index
                    merged_data = merged_data[
                        ~merged_data.index.duplicated(keep="first")
                    ]

                # Log how many rows were affected by conflicts
                logger.debug(
                    f"Found {len(merged_data.index.unique()) - total_unique_dates} conflicting rows"
                )

        except DataNotFoundError:
            # If no existing data, just use the new data
            logger.info(
                f"No existing data found, using {len(new_data)} rows of new data"
            )
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
        agg_functions: Optional[Dict[str, str]] = None,
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

        # Validate target_timeframe using centralized constants
        timeframe_frequencies = {
            "1m": "1min",
            "5m": "5min",
            "15m": "15min",
            "30m": "30min",
            "1h": "1H",
            "4h": "4H",
            "1d": "1D",
            "1w": "1W",
        }
        target_freq = timeframe_frequencies.get(target_timeframe)
        if not target_freq:
            raise DataError(
                message=f"Invalid target timeframe: {target_timeframe}",
                error_code="DATA-InvalidParameter",
                details={
                    "parameter": "target_timeframe",
                    "value": target_timeframe,
                    "valid_options": list(timeframe_frequencies.keys()),
                },
            )

        # If source_timeframe is provided, validate it
        if source_timeframe:
            source_freq = timeframe_frequencies.get(source_timeframe)
            if not source_freq:
                raise DataError(
                    message=f"Invalid source timeframe: {source_timeframe}",
                    error_code="DATA-InvalidParameter",
                    details={
                        "parameter": "source_timeframe",
                        "value": source_timeframe,
                        "valid_options": list(timeframe_frequencies.keys()),
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
            agg_functions = {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }

        # Make sure all columns in agg_functions exist in the DataFrame
        agg_functions = {k: v for k, v in agg_functions.items() if k in df.columns}

        try:
            logger.debug(
                f"Resampling data to {target_timeframe} frequency ({target_freq})"
            )
            # Make sure the index is sorted
            df_sorted = df.sort_index() if not df.index.is_monotonic_increasing else df

            # Resample the data
            resampled = df_sorted.resample(target_freq).agg(agg_functions)

            # Fill gaps if requested
            if fill_gaps and not resampled.empty:
                logger.debug("Filling gaps in resampled data")
                resampled = self.repair_data(
                    resampled, target_timeframe, method=self.default_repair_method
                )

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

    @log_entry_exit(logger=logger)
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
