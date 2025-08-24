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

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from ktrdr.data.gap_classifier import GapClassification, GapClassifier
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
        logger.debug("Initialized GapAnalyzer component")

    def analyze_gaps(
        self,
        existing_data: Optional[pd.DataFrame],
        requested_start: datetime,
        requested_end: datetime,
        timeframe: str,
        symbol: str,
        mode: str = "tail",
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
        if mode == "local":
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
