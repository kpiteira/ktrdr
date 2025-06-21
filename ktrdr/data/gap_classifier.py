"""
Enhanced Gap Classification System

This module provides intelligent gap classification that distinguishes between
expected gaps (weekends, holidays, non-trading hours) and unexpected gaps
that may require investigation or filling.

Integrates with existing trading hours metadata from symbol_discovery_cache.json
and the trading_hours.py infrastructure.
"""

from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone, timedelta, date
from dataclasses import dataclass
import json
import pandas as pd
from pathlib import Path

from ktrdr.logging import get_logger
from ktrdr.data.local_data_loader import TimestampManager
from ktrdr.utils.timezone_utils import TimestampManager
from ktrdr.data.trading_hours import TradingHoursManager
from ktrdr.data.timeframe_constants import TimeframeConstants

logger = get_logger(__name__)


class GapClassification(Enum):
    """Classification types for data gaps."""

    EXPECTED_WEEKEND = "expected_weekend"  # Weekend gaps for daily+ timeframes
    EXPECTED_TRADING_HOURS = "expected_trading_hours"  # Non-trading hours for intraday
    EXPECTED_HOLIDAY = "expected_holiday"  # Likely holidays adjacent to weekends
    MARKET_CLOSURE = "market_closure"  # Extended closures (>3 days)
    UNEXPECTED = "unexpected"  # Gaps that need investigation


@dataclass
class GapInfo:
    """Detailed information about a detected gap."""

    start_time: datetime
    end_time: datetime
    classification: GapClassification
    bars_missing: int
    duration_hours: float
    day_context: str
    note: Optional[str] = None
    symbol: Optional[str] = None
    timeframe: Optional[str] = None


class GapClassifier:
    """
    Enhanced gap classifier that uses trading hours metadata to intelligently
    classify gaps as expected vs unexpected.
    """

    def __init__(self, symbol_cache_path: Optional[str] = None):
        """
        Initialize the gap classifier.

        Args:
            symbol_cache_path: Path to symbol_discovery_cache.json
        """
        self.symbol_cache_path = symbol_cache_path or "data/symbol_discovery_cache.json"
        self.symbol_metadata = self._load_symbol_metadata()

        # Use centralized timeframe constants
        self.timeframe_minutes = TimeframeConstants.TIMEFRAME_MINUTES

        logger.info(
            f"Initialized GapClassifier with {len(self.symbol_metadata)} symbols"
        )

    def _load_symbol_metadata(self) -> Dict[str, Dict]:
        """Load symbol metadata from cache file."""
        try:
            cache_path = Path(self.symbol_cache_path)
            if not cache_path.exists():
                logger.warning(f"Symbol cache not found at {cache_path}")
                return {}

            with open(cache_path, "r") as f:
                data = json.load(f)

            # Extract cache.{symbol} structure
            if "cache" in data:
                return data["cache"]
            else:
                return data

        except Exception as e:
            logger.error(f"Failed to load symbol metadata: {e}")
            return {}

    def classify_gap(
        self, start_time: datetime, end_time: datetime, symbol: str, timeframe: str
    ) -> GapClassification:
        """
        Classify a gap as expected or unexpected based on trading hours metadata.

        Args:
            start_time: Gap start timestamp (UTC)
            end_time: Gap end timestamp (UTC)
            symbol: Trading symbol
            timeframe: Data timeframe

        Returns:
            GapClassification enum value
        """
        # Ensure timestamps are UTC
        start_time = TimestampManager.to_utc(start_time)
        end_time = TimestampManager.to_utc(end_time)

        # Get symbol metadata
        symbol_data = self.symbol_metadata.get(symbol, {})
        trading_hours = symbol_data.get("trading_hours", {})

        # Calculate gap duration
        duration_hours = (end_time - start_time).total_seconds() / 3600

        # First, check for weekend gaps (applies to all timeframes for 24/5 markets like forex)
        if self._spans_weekend(start_time, end_time, trading_hours):
            return GapClassification.EXPECTED_WEEKEND

        # Check for holiday patterns BEFORE market closure check
        # This ensures Christmas/New Year gaps are classified as holidays, not market closures
        if self._is_holiday_gap(start_time, end_time, trading_hours):
            return GapClassification.EXPECTED_HOLIDAY

        # For intraday timeframes, check trading hours
        if self._is_intraday_timeframe(timeframe):
            if self._is_outside_trading_hours(start_time, end_time, trading_hours):
                return GapClassification.EXPECTED_TRADING_HOURS

        # Check for extended market closures (>3 days) - but only after holiday check
        if duration_hours > 72:  # 3 days
            return GapClassification.MARKET_CLOSURE

        # If none of the expected patterns match, it's unexpected
        return GapClassification.UNEXPECTED

    def analyze_gap(
        self,
        start_time: datetime,
        end_time: datetime,
        symbol: str,
        timeframe: str,
        context_data: Optional[pd.DataFrame] = None,
    ) -> GapInfo:
        """
        Perform comprehensive gap analysis including classification and context.

        Args:
            start_time: Gap start timestamp (UTC)
            end_time: Gap end timestamp (UTC)
            symbol: Trading symbol
            timeframe: Data timeframe
            context_data: Optional DataFrame with surrounding data for volume analysis

        Returns:
            GapInfo object with detailed analysis
        """
        # Check for IB "no data available" indicators in surrounding context
        ib_no_data_detected = self._check_ib_no_data_indicators(
            start_time, end_time, context_data
        )

        # Classify the gap
        classification = self.classify_gap(start_time, end_time, symbol, timeframe)

        # If we detected IB "no data" indicators and it's not already classified as expected,
        # consider upgrading to expected classification
        if ib_no_data_detected and classification == GapClassification.UNEXPECTED:
            # Check if this could be reclassified as expected based on IB data indicators
            if self._should_reclassify_based_on_ib_indicators(
                start_time, end_time, symbol, timeframe
            ):
                classification = GapClassification.EXPECTED_TRADING_HOURS

        # Calculate gap metrics
        duration_hours = (end_time - start_time).total_seconds() / 3600
        bars_missing = self._calculate_bars_missing(start_time, end_time, timeframe)
        day_context = self._generate_day_context(start_time, end_time)
        note = self._generate_gap_note(
            classification, start_time, end_time, symbol, timeframe, ib_no_data_detected
        )

        return GapInfo(
            start_time=start_time,
            end_time=end_time,
            classification=classification,
            bars_missing=bars_missing,
            duration_hours=duration_hours,
            day_context=day_context,
            note=note,
            symbol=symbol,
            timeframe=timeframe,
        )

    def _is_intraday_timeframe(self, timeframe: str) -> bool:
        """Check if timeframe is intraday (< 1 day)."""
        return TimeframeConstants.is_intraday(timeframe)

    def _spans_weekend(
        self, start_time: datetime, end_time: datetime, trading_hours: Dict
    ) -> bool:
        """
        Check if gap spans a weekend period.

        Args:
            start_time: Gap start (UTC)
            end_time: Gap end (UTC)
            trading_hours: Trading hours metadata

        Returns:
            True if gap spans weekend
        """
        if not trading_hours:
            # Default behavior: weekends are Saturday-Sunday
            return self._spans_default_weekend(start_time, end_time)

        trading_days = trading_hours.get(
            "trading_days", [0, 1, 2, 3, 4]
        )  # Mon-Fri default
        timezone_str = trading_hours.get("timezone", "UTC")
        regular_hours = trading_hours.get("regular_hours", {})

        try:
            # Convert to exchange timezone
            start_local = start_time.astimezone(
                pd.Timestamp(start_time).tz_convert(timezone_str).tz
            )
            end_local = end_time.astimezone(
                pd.Timestamp(end_time).tz_convert(timezone_str).tz
            )

            # Special handling for 24/5 markets (like forex)
            is_24_5_market = self._is_24_5_market(trading_hours)

            if is_24_5_market:
                # For 24/5 markets, weekend is the gap between Friday close and Sunday open
                return self._is_forex_weekend_gap(start_local, end_local, regular_hours)
            else:
                # For regular markets, check if gap includes non-trading days
                current = start_local
                while current <= end_local:
                    if current.weekday() not in trading_days:
                        return True
                    current += timedelta(days=1)

                return False

        except Exception as e:
            logger.warning(f"Error checking weekend span: {e}, falling back to default")
            return self._spans_default_weekend(start_time, end_time)

    def _spans_default_weekend(self, start_time: datetime, end_time: datetime) -> bool:
        """Default weekend check (Saturday-Sunday)."""
        current = start_time
        while current <= end_time:
            if current.weekday() in [5, 6]:  # Saturday, Sunday
                return True
            current += timedelta(days=1)
        return False

    def _is_24_5_market(self, trading_hours: Dict) -> bool:
        """
        Check if this is a 24/5 market (like forex).

        24/5 markets are characterized by:
        - Trading on Sunday (day 6)
        - Saturday is the only non-trading day
        - Often has 24-hour sessions or cross-midnight sessions
        """
        trading_days = trading_hours.get("trading_days", [])
        regular_hours = trading_hours.get("regular_hours", {})

        # Check if Sunday (6) is a trading day and Saturday (5) is not
        has_sunday = 6 in trading_days
        no_saturday = 5 not in trading_days

        # Check for 24-hour or cross-midnight sessions (like 22:00-21:59)
        session_start = regular_hours.get("start", "")
        session_end = regular_hours.get("end", "")
        is_cross_midnight = False

        if session_start and session_end:
            try:
                start_hour = int(session_start.split(":")[0])
                end_hour = int(session_end.split(":")[0])
                # Cross-midnight if start hour > end hour (like 22:00 to 21:59)
                is_cross_midnight = start_hour > end_hour
            except:
                pass

        return has_sunday and no_saturday and is_cross_midnight

    def _is_forex_weekend_gap(
        self, start_local: pd.Timestamp, end_local: pd.Timestamp, regular_hours: Dict
    ) -> bool:
        """
        Check if gap represents a forex weekend closure.

        Forex weekend pattern:
        - Starts Friday around market close time
        - Ends Sunday around market open time
        - Duration typically 40-50 hours
        """
        gap_duration_hours = (end_local - start_local).total_seconds() / 3600

        # Weekend gaps are typically 40-50 hours for forex
        if not (35 <= gap_duration_hours <= 55):
            return False

        # Check if gap starts on Friday and ends on Sunday
        start_weekday = start_local.weekday()  # Friday = 4
        end_weekday = end_local.weekday()  # Sunday = 6

        # Classic forex weekend: Friday -> Sunday
        if start_weekday == 4 and end_weekday == 6:
            return True

        # Also handle gaps that span Saturday (Friday -> Saturday -> Sunday)
        if start_weekday == 4 and end_weekday == 6 and gap_duration_hours >= 40:
            return True

        return False

    def _is_holiday_gap(
        self, start_time: datetime, end_time: datetime, trading_hours: Dict
    ) -> bool:
        """
        Check if gap represents a holiday period.

        Args:
            start_time: Gap start (UTC)
            end_time: Gap end (UTC)
            trading_hours: Trading hours metadata

        Returns:
            True if gap is during a holiday period
        """
        # First check major holidays
        if self._is_major_holiday_gap(start_time, end_time):
            return True

        # Then check weekend-adjacent patterns
        return self._is_adjacent_to_weekend_gap(start_time, end_time, trading_hours)

    def _is_major_holiday_gap(self, start_time: datetime, end_time: datetime) -> bool:
        """
        Check if gap occurs during major holidays.

        Major holidays that typically affect markets:
        - Christmas: Dec 24-26
        - New Year: Dec 31 - Jan 2
        - Thanksgiving: 4th Thursday in November (US)
        - Good Friday: Variable date
        - Independence Day: July 4 (US)
        """
        # Convert to UTC if needed
        start_utc = TimestampManager.to_utc(start_time)
        end_utc = TimestampManager.to_utc(end_time)

        # Check each day in the gap period
        current = start_utc.date()
        end_date = end_utc.date()

        while current <= end_date:
            if self._is_holiday_date(current):
                return True
            current += timedelta(days=1)

        return False

    def _is_holiday_date(self, date_obj: date) -> bool:
        """Check if a specific date is a major holiday."""
        month = date_obj.month
        day = date_obj.day
        year = date_obj.year

        # Christmas period (Dec 24-26)
        if month == 12 and day in [24, 25, 26]:
            return True

        # New Year period (Dec 31 - Jan 2)
        if (month == 12 and day == 31) or (month == 1 and day in [1, 2]):
            return True

        # Good Friday (variable date - Friday before Easter)
        if self._is_good_friday(date_obj):
            return True

        # Easter Monday (day after Easter)
        if self._is_easter_monday(date_obj):
            return True

        # Martin Luther King Day (3rd Monday in January)
        if month == 1 and self._is_nth_weekday(date_obj, 0, 3):  # 3rd Monday
            return True

        # Presidents Day (3rd Monday in February)
        if month == 2 and self._is_nth_weekday(date_obj, 0, 3):  # 3rd Monday
            return True

        # Memorial Day (last Monday in May)
        if month == 5 and self._is_last_weekday(date_obj, 0):  # Last Monday
            return True

        # Independence Day (July 4, or observed date)
        if month == 7 and day == 4:
            return True
        if (
            month == 7 and day == 3 and date_obj.weekday() == 4
        ):  # Friday before if July 4 is Saturday
            return True
        if (
            month == 7 and day == 5 and date_obj.weekday() == 0
        ):  # Monday after if July 4 is Sunday
            return True

        # Labor Day (1st Monday in September)
        if month == 9 and self._is_nth_weekday(date_obj, 0, 1):  # 1st Monday
            return True

        # Columbus Day (2nd Monday in October)
        if month == 10 and self._is_nth_weekday(date_obj, 0, 2):  # 2nd Monday
            return True

        # Thanksgiving (4th Thursday in November)
        if month == 11 and self._is_nth_weekday(date_obj, 3, 4):  # 4th Thursday
            return True

        # Black Friday (day after Thanksgiving)
        if month == 11 and self._is_nth_weekday(date_obj, 4, 4):  # 4th Friday
            return True

        return False

    def _is_nth_weekday(self, date_obj: date, weekday: int, n: int) -> bool:
        """Check if date is the nth occurrence of weekday in the month."""
        # weekday: 0=Monday, 1=Tuesday, ..., 6=Sunday
        first_day = date_obj.replace(day=1)
        first_weekday = first_day.weekday()

        # Calculate the date of the nth occurrence
        days_to_add = (weekday - first_weekday) % 7 + (n - 1) * 7
        nth_date = first_day + timedelta(days=days_to_add)

        # Check if it's in the same month and matches our date
        return nth_date.month == date_obj.month and nth_date == date_obj

    def _is_last_weekday(self, date_obj: date, weekday: int) -> bool:
        """Check if date is the last occurrence of weekday in the month."""
        # Find the last day of the month
        if date_obj.month == 12:
            last_day = date_obj.replace(
                year=date_obj.year + 1, month=1, day=1
            ) - timedelta(days=1)
        else:
            last_day = date_obj.replace(month=date_obj.month + 1, day=1) - timedelta(
                days=1
            )

        # Work backwards to find the last occurrence of the weekday
        while last_day.weekday() != weekday:
            last_day -= timedelta(days=1)

        return last_day == date_obj

    def _calculate_easter(self, year: int) -> date:
        """
        Calculate Easter date for a given year using the algorithm.

        Args:
            year: Year to calculate Easter for

        Returns:
            Date of Easter Sunday for that year
        """
        # Easter calculation algorithm (Gregorian calendar)
        # Based on the algorithm by Jean Meeus

        a = year % 19
        b = year // 100
        c = year % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        n = (h + l - 7 * m + 114) // 31
        p = (h + l - 7 * m + 114) % 31

        return date(year, n, p + 1)

    def _is_good_friday(self, date_obj: date) -> bool:
        """Check if date is Good Friday (2 days before Easter)."""
        easter = self._calculate_easter(date_obj.year)
        good_friday = easter - timedelta(days=2)
        return date_obj == good_friday

    def _is_easter_monday(self, date_obj: date) -> bool:
        """Check if date is Easter Monday (day after Easter)."""
        easter = self._calculate_easter(date_obj.year)
        easter_monday = easter + timedelta(days=1)
        return date_obj == easter_monday

    def _is_outside_trading_hours(
        self, start_time: datetime, end_time: datetime, trading_hours: Dict
    ) -> bool:
        """
        Check if gap is outside trading hours for intraday timeframes.

        Args:
            start_time: Gap start (UTC)
            end_time: Gap end (UTC)
            trading_hours: Trading hours metadata

        Returns:
            True if gap is outside trading hours
        """
        if not trading_hours:
            # Without trading hours data, assume 24/5 (weekdays only)
            return self._is_outside_default_hours(start_time, end_time)

        timezone_str = trading_hours.get("timezone", "UTC")
        regular_hours = trading_hours.get("regular_hours", {})

        if not regular_hours:
            return False

        try:
            # Convert UTC times to exchange timezone
            if hasattr(start_time, "tz_convert"):
                # Already a pandas timestamp with timezone
                start_local = start_time.tz_convert(timezone_str)
                end_local = end_time.tz_convert(timezone_str)
            else:
                # Convert datetime to pandas timestamp, handling timezone correctly
                if start_time.tzinfo is None:
                    # Naive datetime, assume UTC
                    start_local = pd.Timestamp(start_time, tz="UTC").tz_convert(
                        timezone_str
                    )
                    end_local = pd.Timestamp(end_time, tz="UTC").tz_convert(
                        timezone_str
                    )
                else:
                    # Timezone-aware datetime
                    start_local = pd.Timestamp(start_time).tz_convert(timezone_str)
                    end_local = pd.Timestamp(end_time).tz_convert(timezone_str)

            # Parse trading hours
            start_hour_str = regular_hours.get("start", "09:30")
            end_hour_str = regular_hours.get("end", "16:00")

            # Debug logging
            logger.debug(
                f"Checking trading hours: {start_local} to {end_local} in {timezone_str}"
            )
            logger.debug(f"Trading session: {start_hour_str} to {end_hour_str}")

            # Check if entire gap is outside trading hours
            return self._is_time_range_outside_session(
                start_local, end_local, start_hour_str, end_hour_str
            )

        except Exception as e:
            logger.warning(
                f"Error checking trading hours: {e}, falling back to default"
            )
            return self._is_outside_default_hours(start_time, end_time)

    def _is_outside_default_hours(
        self, start_time: datetime, end_time: datetime
    ) -> bool:
        """Default trading hours check (9:30 AM - 4:00 PM EST)."""
        # Simple check: if gap is during weekend, consider it outside hours
        return self._spans_default_weekend(start_time, end_time)

    def _is_time_range_outside_session(
        self,
        start_local: pd.Timestamp,
        end_local: pd.Timestamp,
        session_start: str,
        session_end: str,
    ) -> bool:
        """
        Check if time range is completely outside trading session.

        Args:
            start_local: Start time in exchange timezone
            end_local: End time in exchange timezone
            session_start: Session start time (HH:MM format)
            session_end: Session end time (HH:MM format)

        Returns:
            True if completely outside session
        """
        try:
            # Parse session times
            start_hour, start_min = map(int, session_start.split(":"))
            end_hour, end_min = map(int, session_end.split(":"))

            # Create session times for the gap day(s)
            gap_start_time = start_local.time()
            gap_end_time = end_local.time()

            # Create session time objects for comparison
            session_start_time = (
                pd.Timestamp.now()
                .replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
                .time()
            )
            session_end_time = (
                pd.Timestamp.now()
                .replace(hour=end_hour, minute=end_min, second=0, microsecond=0)
                .time()
            )

            # Check if gap times are outside trading session
            # For same-day gaps, check if gap is completely outside session
            if start_local.date() == end_local.date():
                # Handle normal sessions (9:30-16:00)
                if session_start_time <= session_end_time:
                    # Gap is outside if it's completely before market open OR completely after market close
                    gap_completely_before = gap_end_time <= session_start_time
                    gap_completely_after = gap_start_time >= session_end_time
                    gap_outside = gap_completely_before or gap_completely_after
                else:
                    # Handle sessions crossing midnight (like 22:00-21:59 for forex)
                    # Gap is outside if it's in the "off" period between session_end and session_start
                    gap_outside = (
                        gap_start_time >= session_end_time
                        and gap_end_time <= session_start_time
                    )

                return gap_outside
            else:
                # Multi-day gaps - more complex analysis needed
                # For now, consider multi-day gaps as potentially spanning trading hours
                return False

        except Exception as e:
            logger.warning(f"Error parsing session times: {e}")
            return False

    def _is_adjacent_to_weekend_gap(
        self, start_time: datetime, end_time: datetime, trading_hours: Dict
    ) -> bool:
        """
        Check if gap is adjacent to weekend (likely holiday pattern).

        Args:
            start_time: Gap start (UTC)
            end_time: Gap end (UTC)
            trading_hours: Trading hours metadata

        Returns:
            True if gap appears to be holiday-related
        """
        # For daily data, check if gap is 1-3 days and adjacent to weekend
        duration_days = (end_time - start_time).total_seconds() / (24 * 3600)

        if duration_days > 3:
            return False  # Too long to be typical holiday

        # Check if gap is adjacent to weekend
        timezone_str = trading_hours.get("timezone", "UTC") if trading_hours else "UTC"

        try:
            start_local = pd.Timestamp(start_time).tz_convert(timezone_str)
            end_local = pd.Timestamp(end_time).tz_convert(timezone_str)

            # Check days before and after gap
            before_gap = start_local - pd.Timedelta(days=1)
            after_gap = end_local + pd.Timedelta(days=1)

            # If gap is surrounded by weekend days, likely holiday
            weekend_days = [5, 6]  # Saturday, Sunday

            if (
                before_gap.weekday() in weekend_days
                or after_gap.weekday() in weekend_days
            ):
                return True

            return False

        except Exception as e:
            logger.warning(f"Error checking holiday pattern: {e}")
            return False

    def _calculate_bars_missing(
        self, start_time: datetime, end_time: datetime, timeframe: str
    ) -> int:
        """
        Calculate approximate number of bars missing in the gap.

        Args:
            start_time: Gap start (UTC)
            end_time: Gap end (UTC)
            timeframe: Data timeframe

        Returns:
            Estimated number of missing bars
        """
        duration_minutes = (end_time - start_time).total_seconds() / 60
        timeframe_minutes = self.timeframe_minutes.get(timeframe, 60)

        return max(1, int(duration_minutes / timeframe_minutes))

    def _generate_day_context(self, start_time: datetime, end_time: datetime) -> str:
        """
        Generate human-readable day context for the gap.

        Args:
            start_time: Gap start (UTC)
            end_time: Gap end (UTC)

        Returns:
            Day context string (e.g., "Monday-Tuesday", "Friday (pre-weekend)")
        """
        try:
            start_day = start_time.strftime("%A")
            end_day = end_time.strftime("%A")

            if start_day == end_day:
                # Same day gap
                if start_time.weekday() == 4:  # Friday
                    return f"{start_day} (pre-weekend)"
                elif start_time.weekday() == 0:  # Monday
                    return f"{start_day} (post-weekend)"
                else:
                    return start_day
            else:
                # Multi-day gap
                return f"{start_day}-{end_day}"

        except Exception:
            return "Unknown"

    def _check_ib_no_data_indicators(
        self,
        start_time: datetime,
        end_time: datetime,
        context_data: Optional[pd.DataFrame],
    ) -> bool:
        """
        Check for IB "no data available" indicators (volume=-1) in surrounding data.

        Args:
            start_time: Gap start time
            end_time: Gap end time
            context_data: DataFrame with surrounding data

        Returns:
            True if IB "no data" indicators are detected
        """
        if (
            context_data is None
            or context_data.empty
            or "volume" not in context_data.columns
        ):
            return False

        # Ensure timezone consistency - convert all to UTC timezone-aware
        start_time = TimestampManager.to_utc(start_time)
        end_time = TimestampManager.to_utc(end_time)

        # Look for volume=-1 in the period around the gap
        gap_window = timedelta(hours=6)  # Look 6 hours before and after gap
        window_start = start_time - gap_window
        window_end = end_time + gap_window

        # Convert to pandas Timestamp for comparison with DataFrame index
        # Handle timezone-aware datetime properly
        if window_start.tzinfo is not None:
            window_start_ts = pd.Timestamp(window_start).tz_convert("UTC")
        else:
            window_start_ts = pd.Timestamp(window_start, tz="UTC")

        if window_end.tzinfo is not None:
            window_end_ts = pd.Timestamp(window_end).tz_convert("UTC")
        else:
            window_end_ts = pd.Timestamp(window_end, tz="UTC")

        # Filter to window around gap
        mask = (context_data.index >= window_start_ts) & (
            context_data.index <= window_end_ts
        )
        window_data = context_data[mask]

        if window_data.empty:
            return False

        # Check for volume=-1 indicators
        no_data_indicators = (window_data["volume"] == -1).sum()
        total_bars = len(window_data)

        # If more than 20% of bars in the window have volume=-1, consider it a "no data" period
        if total_bars > 0 and (no_data_indicators / total_bars) > 0.2:
            logger.debug(
                f"IB 'no data' indicators detected: {no_data_indicators}/{total_bars} bars have volume=-1 around gap {start_time} to {end_time}"
            )
            return True

        return False

    def _should_reclassify_based_on_ib_indicators(
        self, start_time: datetime, end_time: datetime, symbol: str, timeframe: str
    ) -> bool:
        """
        Determine if a gap should be reclassified based on IB data indicators.

        Args:
            start_time: Gap start time
            end_time: Gap end time
            symbol: Trading symbol
            timeframe: Data timeframe

        Returns:
            True if gap should be reclassified as expected
        """
        # Only reclassify short to medium gaps (< 72 hours) that could be data feed issues
        duration_hours = (end_time - start_time).total_seconds() / 3600

        # Don't reclassify very long gaps (likely real market closures)
        if duration_hours > 72:  # 3 days
            return False

        # For forex, be more liberal with reclassification since volume data is unreliable
        if symbol in [
            "EURUSD",
            "GBPUSD",
            "USDJPY",
            "USDCHF",
            "AUDUSD",
            "USDCAD",
            "NZDUSD",
        ]:
            return duration_hours <= 48  # 2 days max for forex

        # For other instruments, be more conservative
        return duration_hours <= 24  # 1 day max for stocks/other

    def _generate_gap_note(
        self,
        classification: GapClassification,
        start_time: datetime,
        end_time: datetime,
        symbol: str,
        timeframe: str,
        ib_no_data_detected: bool = False,
    ) -> str:
        """
        Generate explanatory note for the gap.

        Args:
            classification: Gap classification
            start_time: Gap start (UTC)
            end_time: Gap end (UTC)
            symbol: Trading symbol
            timeframe: Data timeframe
            ib_no_data_detected: Whether IB "no data" indicators were detected

        Returns:
            Human-readable explanation of the gap
        """
        duration_hours = (end_time - start_time).total_seconds() / 3600
        ib_note = " (IB volume=-1 detected)" if ib_no_data_detected else ""

        if classification == GapClassification.EXPECTED_WEEKEND:
            return f"Weekend gap for {timeframe} data - normal market closure{ib_note}"

        elif classification == GapClassification.EXPECTED_TRADING_HOURS:
            base_note = f"Gap outside trading hours for {timeframe} data - normal non-market period"
            if ib_no_data_detected:
                base_note += " (confirmed by IB 'no data' indicators)"
            return base_note

        elif classification == GapClassification.EXPECTED_HOLIDAY:
            return f"Likely holiday gap ({duration_hours:.1f}h) - adjacent to weekend{ib_note}"

        elif classification == GapClassification.MARKET_CLOSURE:
            return f"Extended market closure ({duration_hours/24:.1f} days) - investigate broker/exchange{ib_note}"

        elif classification == GapClassification.UNEXPECTED:
            base_note = f"Unexpected gap ({duration_hours:.1f}h) during trading period - needs investigation"
            if ib_no_data_detected:
                base_note += " (IB volume=-1 suggests data feed issue)"
            return base_note

        else:
            return f"Gap of {duration_hours:.1f} hours{ib_note}"

    def get_symbol_trading_hours(self, symbol: str) -> Optional[Dict]:
        """
        Get trading hours metadata for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Trading hours dictionary or None if not found
        """
        symbol_data = self.symbol_metadata.get(symbol, {})
        return symbol_data.get("trading_hours")

    def is_gap_worth_filling(
        self,
        gap_info: GapInfo,
        priority_threshold: GapClassification = GapClassification.UNEXPECTED,
    ) -> bool:
        """
        Determine if a gap is worth filling based on classification.

        Args:
            gap_info: Gap information
            priority_threshold: Minimum classification level to fill

        Returns:
            True if gap should be filled
        """
        # Priority order (lower value = higher priority)
        priority_order = {
            GapClassification.UNEXPECTED: 1,
            GapClassification.MARKET_CLOSURE: 2,
            GapClassification.EXPECTED_HOLIDAY: 3,
            GapClassification.EXPECTED_TRADING_HOURS: 4,
            GapClassification.EXPECTED_WEEKEND: 5,
        }

        gap_priority = priority_order.get(gap_info.classification, 5)
        threshold_priority = priority_order.get(priority_threshold, 1)

        return gap_priority <= threshold_priority
