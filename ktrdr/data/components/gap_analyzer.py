"""
GapAnalyzer Component

Extracted gap analysis logic from DataManager to provide a dedicated
component for analyzing data gaps with mode-aware behavior.

This component handles:
- Gap detection between requested and existing data
- Mode-specific gap filtering (local, tail, backfill, full)
- Internal gap discovery within existing data
- Meaningful gap determination based on timeframe
- Trading day validation for gap classification
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import pandas as pd

from ktrdr.data.components.progress_manager import ProgressManager
from ktrdr.data.gap_classifier import GapClassification, GapClassifier
from ktrdr.data.loading_modes import DataLoadingMode
from ktrdr.data.timeframe_constants import TimeframeConstants
from ktrdr.logging import get_logger

logger = get_logger(__name__)


class GapAnalyzer:
    """
    Component for analyzing data gaps with intelligent classification.

    Provides gap analysis functionality extracted from DataManager
    with support for different loading modes and intelligent gap filtering.
    """

    def __init__(self, gap_classifier: Optional[GapClassifier] = None):
        """
        Initialize the GapAnalyzer.

        Args:
            gap_classifier: GapClassifier instance for intelligent gap classification.
                           If None, a default instance will be created.
        """
        self.gap_classifier = gap_classifier or GapClassifier()

        # Mode-aware analysis state
        self.current_mode: Optional[DataLoadingMode] = None
        self.progress_manager: Optional[ProgressManager] = None

        # Configuration options for analysis strategies and performance
        self.config: dict[str, Any] = {
            # Minimum gap duration to consider for analysis (prevents noise from minor gaps)
            "min_gap_threshold": timedelta(hours=1),
            # Performance safety limit - max gaps to process per mode to prevent memory issues
            "max_gaps_per_mode": 1000,
            # Whether to give priority to weekend gaps in FULL mode analysis
            "prioritize_weekends": True,
            # Skip holiday detection for performance (holidays will be classified as regular gaps)
            "skip_holiday_analysis": False,
            # Performance monitoring (tracks analysis duration and memory usage)
            "enable_performance_monitoring": False,
        }

        logger.debug("Initialized GapAnalyzer component with mode-aware capabilities")

    def analyze_gaps(
        self,
        existing_data: Optional[pd.DataFrame],
        requested_start: datetime,
        requested_end: datetime,
        timeframe: str,
        symbol: str,
        mode: DataLoadingMode = DataLoadingMode.TAIL,
    ) -> list[tuple[datetime, datetime]]:
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
            mode: Loading mode ('local', 'tail', 'backfill', 'full')

        Returns:
            List of (start_time, end_time) tuples representing gaps to fill
        """
        # Local mode returns no gaps - use existing data only
        if mode == DataLoadingMode.LOCAL:
            return []

        gaps_to_fill = []

        # If no existing data, entire range is a gap to fill
        if existing_data is None or existing_data.empty:
            logger.info(
                f"No existing data found - entire range is a gap: {requested_start} to {requested_end}"
            )
            return [(requested_start, requested_end)]

        # Ensure timezone consistency
        if existing_data.index.tz is None:  # type: ignore
            existing_data.index = existing_data.index.tz_localize("UTC")  # type: ignore
        elif existing_data.index.tz != requested_start.tzinfo:  # type: ignore
            existing_data.index = existing_data.index.tz_convert(requested_start.tzinfo)  # type: ignore

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
                "🚀 BACKFILL MODE: Skipping micro-gap analysis to focus on large historical periods"
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
                # SAFEGUARD: Skip gaps <2 days when trading hours data is missing
                # This prevents unnecessary IB requests when we can't properly classify gaps
                if gap_duration < timedelta(days=2):
                    # Check if we have trading hours data for this symbol
                    symbol_metadata = self.gap_classifier.symbol_metadata.get(
                        symbol, {}
                    )
                    trading_hours = symbol_metadata.get("trading_hours", {})

                    if not trading_hours:
                        logger.info(
                            f"⚠️  SAFEGUARD ACTIVATED: Skipping gap <2 days with missing trading hours: {gap_start} → {gap_end} (duration: {gap_duration})"
                        )
                        continue

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
                    logger.info(
                        f"📍 UNEXPECTED GAP TO FILL: {gap_start} → {gap_end} ({gap_info.classification.value}) duration={gap_duration}"
                    )
                else:
                    logger.info(
                        f"📅 EXPECTED GAP SKIPPED: {gap_start} → {gap_end} ({gap_info.classification.value}) duration={gap_duration} - {gap_info.note}"
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
    ) -> list[tuple[datetime, datetime]]:
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
        gaps: list[tuple[datetime, datetime]] = []

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

    # Mode-aware functionality starts here

    def set_analysis_mode(self, mode: DataLoadingMode) -> None:
        """
        Configure mode-specific behavior for gap analysis.

        Args:
            mode: DataLoadingMode enum value

        Raises:
            ValueError: If mode is invalid
        """
        if not isinstance(mode, DataLoadingMode):
            raise ValueError(f"Invalid analysis mode: {mode}")

        self.current_mode = mode
        logger.debug(f"Set analysis mode to {mode.value}")

    def set_progress_manager(self, progress_manager: ProgressManager) -> None:
        """
        Set the ProgressManager for analysis progress reporting.

        Args:
            progress_manager: ProgressManager instance
        """
        self.progress_manager = progress_manager
        logger.debug("Set ProgressManager for gap analysis progress reporting")

    def set_configuration(self, config: dict[str, Any]) -> None:
        """
        Set configuration options for analysis strategies and thresholds.

        Args:
            config: Configuration dictionary
        """
        self.config.update(config)
        logger.debug(f"Updated gap analyzer configuration: {config}")

    def classify_gap_type(
        self,
        gap_start: datetime,
        gap_end: datetime,
        market_calendar: Any,
        symbol: str,
        timeframe: str,
    ) -> str:
        """
        Classify gap type with market calendar integration.

        Args:
            gap_start: Gap start time
            gap_end: Gap end time
            market_calendar: Market calendar instance
            symbol: Trading symbol
            timeframe: Data timeframe

        Returns:
            Gap type classification string
        """
        gap_duration = gap_end - gap_start

        # Check for holidays
        try:
            if hasattr(market_calendar, "holidays"):
                holidays = market_calendar.holidays(gap_start.date(), gap_end.date())
                if len(holidays) > 0:
                    return "holiday"
        except Exception as e:
            logger.debug(f"Holiday check failed: {e}")

        # Check for weekends
        if gap_start.weekday() >= 5 or gap_end.weekday() >= 5:  # Saturday/Sunday
            if gap_duration <= timedelta(days=3):  # Normal weekend
                return "market_closure"

        # NOTE: Trading hours classification is not implemented
        # This would require proper timezone handling and exchange-specific calendars
        # For production use, integrate pandas_market_calendars or similar library

        # Default classification
        if gap_duration > timedelta(days=3):
            return "market_closure"
        else:
            return "missing_data"

    def prioritize_gaps_by_mode(
        self, gaps: list[Any], mode: DataLoadingMode
    ) -> list[Any]:
        """
        Prioritize gaps based on mode and data characteristics.

        Args:
            gaps: List of gap objects
            mode: Loading mode

        Returns:
            Prioritized list of gaps
        """
        if mode == DataLoadingMode.LOCAL:
            return []  # No gaps needed for local mode

        if not gaps:
            return []

        prioritized = gaps.copy()

        if mode == DataLoadingMode.TAIL:
            # Prioritize recent gaps first (newest to oldest)
            prioritized.sort(key=lambda g: g.start_time, reverse=True)

        elif mode == DataLoadingMode.BACKFILL:
            # Prioritize historical gaps first (oldest to newest)
            prioritized.sort(key=lambda g: g.start_time)

        elif mode == DataLoadingMode.FULL:
            # Prioritize by importance first, then strategically
            def gap_priority_key(gap):
                # Higher priority numbers come first
                priority = getattr(gap, "priority", 1)
                # Missing data is more important than market closures
                type_priority = (
                    2 if getattr(gap, "gap_type", "") == "missing_data" else 1
                )
                return (-priority, -type_priority, gap.start_time)

            prioritized.sort(key=gap_priority_key)

        # Limit gaps per mode configuration
        max_gaps = self.config.get("max_gaps_per_mode", 1000)
        return prioritized[:max_gaps]

    def analyze_gaps_by_mode(
        self,
        mode: DataLoadingMode,
        existing_data: Optional[pd.DataFrame],
        requested_start: datetime,
        requested_end: datetime,
        timeframe: str,
        symbol: str,
        **kwargs,
    ) -> list[tuple[datetime, datetime]]:
        """
        Analyze gaps using mode-specific strategies with optional performance monitoring.

        Args:
            mode: Data loading mode
            existing_data: Existing DataFrame with data
            requested_start: Start of requested range
            requested_end: End of requested range
            timeframe: Data timeframe
            symbol: Trading symbol
            **kwargs: Additional arguments

        Returns:
            List of gaps to fill as (start, end) tuples
        """
        start_time = (
            time.time()
            if self.config.get("enable_performance_monitoring", False)
            else 0
        )

        # Validate inputs
        if requested_start >= requested_end:
            raise ValueError("Start date must be before end date")

        # Validate timeframe
        valid_timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]
        if timeframe not in valid_timeframes:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        # Perform mode-specific analysis
        if mode == DataLoadingMode.LOCAL:
            gaps = []  # No analysis needed
        elif mode == DataLoadingMode.TAIL:
            gaps = self._analyze_recent_gaps(
                existing_data,
                requested_start,
                requested_end,
                timeframe,
                symbol,
                **kwargs,
            )
        elif mode == DataLoadingMode.BACKFILL:
            gaps = self._analyze_historical_gaps(
                existing_data,
                requested_start,
                requested_end,
                timeframe,
                symbol,
                **kwargs,
            )
        elif mode == DataLoadingMode.FULL:
            gaps = self._analyze_complete_range(
                existing_data,
                requested_start,
                requested_end,
                timeframe,
                symbol,
                **kwargs,
            )
        else:
            raise ValueError(f"Unknown mode: {mode}")

        # Performance monitoring
        if self.config.get("enable_performance_monitoring", False):
            date_range_days = (requested_end - requested_start).days
            self._monitor_performance(
                f"analyze_gaps_by_mode({mode.value})",
                start_time,
                symbol=symbol,
                timeframe=timeframe,
                date_range_days=date_range_days,
                gaps_found=len(gaps),
            )

        return gaps

    def _analyze_recent_gaps(
        self,
        existing_data: Optional[pd.DataFrame],
        requested_start: datetime,
        requested_end: datetime,
        timeframe: str,
        symbol: str,
        **kwargs,
    ) -> list[tuple[datetime, datetime]]:
        """
        TAIL MODE: Analyze gaps from last existing data point to requested end.

        This method implements TRUE tail-specific logic by only analyzing
        gaps that occur AFTER the existing data, ignoring historical gaps.

        Returns:
            List of recent gaps to fill
        """
        if self.progress_manager:
            self.progress_manager.start_operation(1, "Analyzing recent gaps")

        try:
            gaps_to_fill = []

            # TAIL-SPECIFIC: Only analyze from last data point forward
            if existing_data is None or existing_data.empty:
                # No existing data - entire range is a gap
                gaps_to_fill.append((requested_start, requested_end))
            else:
                # Find the last timestamp in existing data
                last_data_time = existing_data.index[-1]

                # Convert to timezone-aware if needed
                if last_data_time.tzinfo is None and requested_end.tzinfo is not None:
                    last_data_time = last_data_time.replace(tzinfo=timezone.utc)
                elif last_data_time.tzinfo is not None and requested_end.tzinfo is None:
                    requested_end = requested_end.replace(tzinfo=timezone.utc)

                # TAIL-SPECIFIC: Only gaps AFTER existing data matter
                if last_data_time < requested_end:
                    # Calculate next expected data point
                    next_expected = self._calculate_next_expected_time(
                        last_data_time, timeframe
                    )

                    # Only add gap if there's meaningful time difference
                    if self._is_meaningful_gap(next_expected, requested_end, timeframe):
                        gaps_to_fill.append((next_expected, requested_end))

            logger.debug(f"🎯 TAIL MODE: Found {len(gaps_to_fill)} recent gaps to fill")
            return gaps_to_fill

        finally:
            if self.progress_manager:
                self.progress_manager.complete_operation()

    def _analyze_historical_gaps(
        self,
        existing_data: Optional[pd.DataFrame],
        requested_start: datetime,
        requested_end: datetime,
        timeframe: str,
        symbol: str,
        **kwargs,
    ) -> list[tuple[datetime, datetime]]:
        """
        BACKFILL MODE: Analyze gaps from requested start to first existing data point.

        This method implements TRUE backfill-specific logic by only analyzing
        gaps that occur BEFORE the existing data, ignoring future gaps.

        Returns:
            List of historical gaps to fill
        """
        if self.progress_manager:
            self.progress_manager.start_operation(1, "Analyzing historical gaps")

        try:
            gaps_to_fill = []

            # BACKFILL-SPECIFIC: Only analyze up to first data point
            if existing_data is None or existing_data.empty:
                # No existing data - entire range is a gap
                gaps_to_fill.append((requested_start, requested_end))
            else:
                # Find the first timestamp in existing data
                first_data_time = existing_data.index[0]

                # Convert to timezone-aware if needed
                if (
                    first_data_time.tzinfo is None
                    and requested_start.tzinfo is not None
                ):
                    first_data_time = first_data_time.tz_localize("UTC")
                elif (
                    first_data_time.tzinfo is not None
                    and requested_start.tzinfo is None
                ):
                    requested_start = requested_start.replace(tzinfo=timezone.utc)

                # BACKFILL-SPECIFIC: Only gaps BEFORE existing data matter
                if requested_start < first_data_time:
                    # Calculate previous expected data point
                    prev_expected = self._calculate_previous_expected_time(
                        first_data_time, timeframe
                    )

                    # Only add gap if there's meaningful time difference
                    if self._is_meaningful_gap(
                        requested_start, prev_expected, timeframe
                    ):
                        gaps_to_fill.append((requested_start, prev_expected))

            logger.debug(
                f"📚 BACKFILL MODE: Found {len(gaps_to_fill)} historical gaps to fill"
            )
            return gaps_to_fill

        finally:
            if self.progress_manager:
                self.progress_manager.complete_operation()

    def _analyze_complete_range(
        self,
        existing_data: Optional[pd.DataFrame],
        requested_start: datetime,
        requested_end: datetime,
        timeframe: str,
        symbol: str,
        **kwargs,
    ) -> list[tuple[datetime, datetime]]:
        """
        FULL MODE: Comprehensive gap analysis for entire requested range.

        This method implements TRUE full-range logic by combining:
        1. Backfill gaps (before existing data)
        2. Internal gaps (within existing data)
        3. Tail gaps (after existing data)

        Returns:
            List of all gaps to fill, ordered for optimal fetching
        """
        if self.progress_manager:
            self.progress_manager.start_operation(1, "Analyzing complete range")

        try:
            gaps_to_fill = []

            # FULL-SPECIFIC: Comprehensive three-phase analysis
            if existing_data is None or existing_data.empty:
                # No existing data - entire range is a gap
                gaps_to_fill.append((requested_start, requested_end))
            else:
                first_data_time = existing_data.index[0]
                last_data_time = existing_data.index[-1]

                # Ensure timezone consistency
                if (
                    first_data_time.tzinfo is None
                    and requested_start.tzinfo is not None
                ):
                    first_data_time = first_data_time.tz_localize("UTC")
                    last_data_time = last_data_time.tz_localize("UTC")
                elif (
                    first_data_time.tzinfo is not None
                    and requested_start.tzinfo is None
                ):
                    requested_start = requested_start.replace(tzinfo=timezone.utc)
                    requested_end = requested_end.replace(tzinfo=timezone.utc)

                # Phase 1: Backfill gaps (before existing data)
                if requested_start < first_data_time:
                    prev_expected = self._calculate_previous_expected_time(
                        first_data_time, timeframe
                    )
                    if self._is_meaningful_gap(
                        requested_start, prev_expected, timeframe
                    ):
                        gaps_to_fill.append((requested_start, prev_expected))

                # Phase 2: Internal gaps (within existing data range)
                internal_gaps = self._find_internal_gaps(
                    existing_data,
                    max(requested_start, first_data_time),
                    min(requested_end, last_data_time),
                    timeframe,
                )
                gaps_to_fill.extend(internal_gaps)

                # Phase 3: Tail gaps (after existing data)
                if last_data_time < requested_end:
                    next_expected = self._calculate_next_expected_time(
                        last_data_time, timeframe
                    )
                    if self._is_meaningful_gap(next_expected, requested_end, timeframe):
                        gaps_to_fill.append((next_expected, requested_end))

            # FULL-SPECIFIC: Intelligent ordering for optimal fetch strategy
            if gaps_to_fill:
                current_time = datetime.now(tz=requested_end.tzinfo)

                # Separate by recency for smart ordering
                recent_gaps = [
                    g for g in gaps_to_fill if (current_time - g[1]).days <= 7
                ]
                older_gaps = [g for g in gaps_to_fill if (current_time - g[1]).days > 7]

                # Recent gaps: most recent first (tail-like behavior)
                recent_gaps.sort(key=lambda g: g[1], reverse=True)
                # Older gaps: chronological order (backfill-like behavior)
                older_gaps.sort(key=lambda g: g[0])

                # Combine with recent gaps prioritized
                gaps_to_fill = recent_gaps + older_gaps

            logger.debug(
                f"⚡ FULL MODE: Found {len(gaps_to_fill)} total gaps across complete range"
            )
            return gaps_to_fill

        finally:
            if self.progress_manager:
                self.progress_manager.complete_operation()

    def estimate_analysis_time(
        self, start_date: datetime, end_date: datetime, mode: DataLoadingMode
    ) -> timedelta:
        """
        Estimate time needed for gap analysis based on date range, mode, and historical performance.

        Args:
            start_date: Analysis start date
            end_date: Analysis end date
            mode: Loading mode

        Returns:
            Estimated analysis time based on historical performance data
        """
        if mode == DataLoadingMode.LOCAL:
            return timedelta(0)  # No analysis needed

        date_range_days = (end_date - start_date).days

        # Base time estimates by mode (calibrated from performance testing)
        # These can be updated based on actual system performance metrics
        time_per_day = {
            DataLoadingMode.LOCAL: 0,
            DataLoadingMode.TAIL: 0.001,  # 1ms per day (optimized for recent data)
            DataLoadingMode.BACKFILL: 0.002,  # 2ms per day (more complex historical analysis)
            DataLoadingMode.FULL: 0.003,  # 3ms per day (comprehensive analysis)
        }

        base_seconds = time_per_day[mode] * date_range_days

        # Add dynamic overhead based on configuration complexity
        overhead = 0.1  # Base 100ms overhead
        if not self.config.get("skip_holiday_analysis", False):
            overhead += 0.05  # Additional 50ms for holiday analysis
        if self.config.get("enable_performance_monitoring", False):
            overhead += 0.02  # Additional 20ms for performance tracking

        total_seconds = base_seconds + overhead

        # Performance monitoring: log estimation for calibration
        if self.config.get("enable_performance_monitoring", False):
            logger.debug(
                f"Gap analysis estimate: {total_seconds:.3f}s for {date_range_days} days in {mode.value} mode"
            )

        return timedelta(seconds=total_seconds)

    def _calculate_next_expected_time(
        self, current_time: datetime, timeframe: str
    ) -> datetime:
        """Calculate the next expected data point based on timeframe."""
        timeframe_minutes = self._timeframe_to_minutes(timeframe)
        return current_time + timedelta(minutes=timeframe_minutes)

    def _calculate_previous_expected_time(
        self, current_time: datetime, timeframe: str
    ) -> datetime:
        """Calculate the previous expected data point based on timeframe."""
        timeframe_minutes = self._timeframe_to_minutes(timeframe)
        return current_time - timedelta(minutes=timeframe_minutes)

    def _timeframe_to_minutes(self, timeframe: str) -> int:
        """Convert timeframe string to minutes."""
        timeframe_map = {
            "1m": 1,
            "2m": 2,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "2h": 120,
            "4h": 240,
            "1d": 1440,
        }
        return timeframe_map.get(timeframe, 60)  # Default to 1 hour

    def get_mode_step_descriptions(self, mode: DataLoadingMode) -> list[str]:
        """
        Get mode-specific step descriptions for progress reporting.

        Args:
            mode: Data loading mode

        Returns:
            List of step descriptions for the mode
        """
        descriptions = {
            DataLoadingMode.LOCAL: ["Skipping analysis (local mode)"],
            DataLoadingMode.TAIL: ["Analyzing recent gaps", "Prioritizing tail data"],
            DataLoadingMode.BACKFILL: [
                "Analyzing historical gaps",
                "Prioritizing backfill data",
            ],
            DataLoadingMode.FULL: [
                "Analyzing complete range",
                "Combining strategies",
                "Prioritizing all gaps",
            ],
        }

        return descriptions.get(mode, ["Analyzing gaps"])

    def _monitor_performance(
        self, operation_name: str, start_time: float, **kwargs
    ) -> None:
        """
        Monitor and log performance metrics for gap analysis operations.

        Args:
            operation_name: Name of the operation being monitored
            start_time: Start time from time.time()
            **kwargs: Additional context for logging
        """
        if not self.config.get("enable_performance_monitoring", False):
            return

        duration = time.time() - start_time
        logger.info(
            f"Performance: {operation_name} completed in {duration:.3f}s",
            extra={"operation": operation_name, "duration_seconds": duration, **kwargs},
        )
