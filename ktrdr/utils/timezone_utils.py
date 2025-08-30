"""
Centralized timestamp and timezone handling utilities.

This module implements the "Always UTC Internally, Display Locally" principle
for consistent timezone handling across all KTRDR data paths.

Core Principle:
- All internal data manipulation uses UTC timestamps
- Only endpoints (CLI/UI) convert to local timezone for display
- Prevents timezone inconsistencies between data paths
"""

from datetime import datetime
from typing import Optional, Union

import pandas as pd

from ktrdr.logging import get_logger

logger = get_logger(__name__)


class TimestampManager:
    """
    Centralized timestamp handling - always UTC internally.

    This class ensures consistent timezone conversion across all data paths:
    - IB data fetcher
    - Fallback data loader
    - API data transformations
    - Frontend chart data
    - Database storage
    - CSV files
    """

    @staticmethod
    def to_utc(dt: Union[datetime, pd.Timestamp, str, None]) -> Optional[pd.Timestamp]:
        """
        Convert any datetime to UTC timezone-aware timestamp.

        Args:
            dt: Datetime to convert (datetime, pd.Timestamp, str, or None)

        Returns:
            UTC timezone-aware pd.Timestamp or None if input is None

        Raises:
            ValueError: If datetime format is invalid
        """
        if dt is None:
            return None

        try:
            # Convert string to pandas timestamp
            if isinstance(dt, str):
                dt = pd.to_datetime(dt)

            # Convert datetime to pandas timestamp
            if isinstance(dt, datetime):
                dt = pd.Timestamp(dt)

            # Ensure it's a pandas timestamp
            if not isinstance(dt, pd.Timestamp):
                dt = pd.Timestamp(dt)

            # Handle timezone conversion
            if dt.tz is None:
                # Assume UTC if no timezone info (defensive approach)
                logger.debug(f"Converting timezone-naive timestamp to UTC: {dt}")
                return dt.tz_localize("UTC")
            else:
                # Convert to UTC from any timezone
                if str(dt.tz) != "UTC":
                    logger.debug(f"Converting {dt.tz} timestamp to UTC: {dt}")
                    return dt.tz_convert("UTC")
                else:
                    return dt

        except Exception as e:
            logger.error(f"Failed to convert timestamp to UTC: {dt}, error: {e}")
            raise ValueError(f"Invalid datetime format: {dt}") from e

    @staticmethod
    def to_exchange_time(utc_timestamp: pd.Timestamp, exchange_tz: str) -> pd.Timestamp:
        """
        Convert UTC timestamp to exchange timezone (for display only).

        Args:
            utc_timestamp: UTC timezone-aware timestamp
            exchange_tz: Exchange timezone string (e.g., 'America/New_York')

        Returns:
            Timestamp converted to exchange timezone

        Raises:
            ValueError: If timestamp is not UTC or timezone is invalid
        """
        if utc_timestamp is None:
            raise ValueError("UTC timestamp cannot be None")

        if str(utc_timestamp.tz) != "UTC":
            raise ValueError(f"Expected UTC timestamp, got: {utc_timestamp.tz}")

        try:
            return utc_timestamp.tz_convert(exchange_tz)
        except Exception as e:
            logger.error(
                f"Failed to convert UTC to {exchange_tz}: {utc_timestamp}, error: {e}"
            )
            raise ValueError(f"Invalid exchange timezone: {exchange_tz}") from e

    @staticmethod
    def format_for_display(utc_timestamp: pd.Timestamp, display_tz: str = "UTC") -> str:
        """
        Format UTC timestamp for display in specified timezone.

        Args:
            utc_timestamp: UTC timezone-aware timestamp
            display_tz: Timezone for display (default: 'UTC')

        Returns:
            Formatted timestamp string
        """
        if utc_timestamp is None:
            return "N/A"

        try:
            if display_tz == "UTC":
                return utc_timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
            else:
                local_time = TimestampManager.to_exchange_time(
                    utc_timestamp, display_tz
                )
                return local_time.strftime("%Y-%m-%d %H:%M:%S %Z")
        except Exception as e:
            logger.error(
                f"Failed to format timestamp for display: {utc_timestamp}, tz: {display_tz}, error: {e}"
            )
            return f"ERROR: {utc_timestamp}"

    @staticmethod
    def convert_dataframe_index(df: pd.DataFrame) -> pd.DataFrame:
        """
        Convert DataFrame index to UTC timezone.

        Args:
            df: DataFrame with datetime index

        Returns:
            DataFrame with UTC timezone-aware index

        Raises:
            ValueError: If DataFrame has no datetime index
        """
        if df is None or df.empty:
            return df

        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("DataFrame must have a DatetimeIndex")

        # Create a copy to avoid modifying original
        df_copy = df.copy()

        # Convert index to UTC
        df_copy.index = TimestampManager.to_utc_series(df_copy.index)

        return df_copy

    @staticmethod
    def to_utc_series(datetime_series: pd.DatetimeIndex) -> pd.DatetimeIndex:
        """
        Convert pandas DatetimeIndex to UTC.

        Args:
            datetime_series: DatetimeIndex to convert

        Returns:
            UTC timezone-aware DatetimeIndex
        """
        if datetime_series.tz is None:
            logger.debug("Converting timezone-naive DatetimeIndex to UTC")
            return datetime_series.tz_localize("UTC")
        else:
            if str(datetime_series.tz) != "UTC":
                logger.debug(f"Converting {datetime_series.tz} DatetimeIndex to UTC")
                return datetime_series.tz_convert("UTC")
            else:
                return datetime_series

    @staticmethod
    def validate_timezone_consistency(
        df: pd.DataFrame, operation_name: str = "operation"
    ) -> None:
        """
        Validate that DataFrame has proper UTC timezone.

        Args:
            df: DataFrame to validate
            operation_name: Name of operation for error messages

        Raises:
            ValueError: If DataFrame has timezone issues
        """
        if df is None or df.empty:
            return

        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError(f"{operation_name}: DataFrame must have a DatetimeIndex")

        if df.index.tz is None:
            raise ValueError(f"{operation_name}: DataFrame has timezone-naive index!")

        if str(df.index.tz) != "UTC":
            raise ValueError(
                f"{operation_name}: DataFrame has non-UTC timezone: {df.index.tz}"
            )

        # Additional sanity checks
        if len(df) > 0:
            first_ts = df.index[0]
            last_ts = df.index[-1]
            logger.debug(
                f"{operation_name}: Timezone validation passed - {first_ts} to {last_ts} (UTC)"
            )

    @staticmethod
    def now_utc() -> pd.Timestamp:
        """
        Get current timestamp in UTC.

        Returns:
            Current UTC timestamp
        """
        return pd.Timestamp.now(tz="UTC")

    @staticmethod
    def is_market_hours(
        timestamp: pd.Timestamp, exchange_tz: str = "America/New_York"
    ) -> bool:
        """
        Check if timestamp falls within regular market hours.

        Args:
            timestamp: UTC timestamp to check
            exchange_tz: Exchange timezone (default: US Eastern)

        Returns:
            True if within regular market hours (9:30 AM - 4:00 PM exchange time)
        """
        try:
            # Convert to exchange time
            local_time = TimestampManager.to_exchange_time(timestamp, exchange_tz)

            # Check if weekday (Monday = 0, Sunday = 6)
            if local_time.weekday() >= 5:  # Saturday or Sunday
                return False

            # Check time (9:30 AM - 4:00 PM)
            market_open = local_time.replace(hour=9, minute=30, second=0, microsecond=0)
            market_close = local_time.replace(
                hour=16, minute=0, second=0, microsecond=0
            )

            return market_open <= local_time <= market_close

        except Exception as e:
            logger.warning(f"Error checking market hours for {timestamp}: {e}")
            return False

    @staticmethod
    def get_trading_session(
        timestamp: pd.Timestamp, exchange_tz: str = "America/New_York"
    ) -> str:
        """
        Determine trading session for a timestamp.

        Args:
            timestamp: UTC timestamp
            exchange_tz: Exchange timezone

        Returns:
            Trading session: 'pre_market', 'regular', 'after_hours', or 'closed'
        """
        try:
            # Convert to exchange time
            local_time = TimestampManager.to_exchange_time(timestamp, exchange_tz)

            # Check if weekend
            if local_time.weekday() >= 5:  # Saturday or Sunday
                return "closed"

            hour = local_time.hour
            minute = local_time.minute

            # Define session times (US Eastern)
            if (
                (hour == 4 and minute >= 0)
                or (4 < hour < 9)
                or (hour == 9 and minute < 30)
            ):
                return "pre_market"
            elif (
                (hour == 9 and minute >= 30)
                or (9 < hour < 16)
                or (hour == 16 and minute == 0)
            ):
                return "regular"
            elif (
                (hour == 16 and minute > 0)
                or (16 < hour < 20)
                or (hour == 20 and minute == 0)
            ):
                return "after_hours"
            else:
                return "closed"

        except Exception as e:
            logger.warning(f"Error determining trading session for {timestamp}: {e}")
            return "unknown"

    @staticmethod
    def is_market_hours_enhanced(
        timestamp: pd.Timestamp,
        symbol: str = None,
        exchange_tz: str = "America/New_York",
    ) -> bool:
        """
        Enhanced market hours check using symbol-specific trading hours metadata.

        Args:
            timestamp: UTC timestamp to check
            symbol: Optional symbol to get specific trading hours
            exchange_tz: Exchange timezone (default: US Eastern, used if no symbol provided)

        Returns:
            True if within regular market hours
        """
        try:
            # If symbol provided, try to get specific trading hours
            if symbol:
                try:
                    from ktrdr.data.trading_hours import TradingHoursManager

                    # Try to get symbol-specific trading hours from cache
                    symbol_info = TimestampManager._get_symbol_trading_hours(symbol)
                    if symbol_info and symbol_info.get("trading_hours"):
                        exchange = symbol_info["exchange"]
                        asset_type = symbol_info["asset_type"]
                        return TradingHoursManager.is_market_open(
                            timestamp, exchange, asset_type
                        )
                except Exception as e:
                    logger.debug(
                        f"Could not get symbol-specific trading hours for {symbol}: {e}"
                    )

            # Fall back to generic US market hours check
            return TimestampManager.is_market_hours(timestamp, exchange_tz)

        except Exception as e:
            logger.error(
                f"Failed enhanced market hours check: {timestamp}, symbol: {symbol}, error: {e}"
            )
            return False

    @staticmethod
    def get_market_status_enhanced(timestamp: pd.Timestamp, symbol: str = None) -> str:
        """
        Get detailed market status using symbol-specific trading hours.

        Args:
            timestamp: UTC timestamp to check
            symbol: Optional symbol to get specific trading hours

        Returns:
            Market status string ("Open", "Closed", "Pre-Market", "After-Hours", "Unknown")
        """
        try:
            # If symbol provided, try to get specific trading hours
            if symbol:
                try:
                    from ktrdr.data.trading_hours import TradingHoursManager

                    symbol_info = TimestampManager._get_symbol_trading_hours(symbol)
                    if symbol_info and symbol_info.get("trading_hours"):
                        exchange = symbol_info["exchange"]
                        asset_type = symbol_info["asset_type"]
                        return TradingHoursManager.get_market_status(
                            timestamp, exchange, asset_type
                        )
                except Exception as e:
                    logger.debug(
                        f"Could not get symbol-specific market status for {symbol}: {e}"
                    )

            # Fall back to generic trading session
            return TimestampManager.get_trading_session(timestamp)

        except Exception as e:
            logger.error(
                f"Failed enhanced market status check: {timestamp}, symbol: {symbol}, error: {e}"
            )
            return "Unknown"

    @staticmethod
    def _get_symbol_trading_hours(symbol: str) -> Optional[dict]:
        """
        Get trading hours metadata for a symbol from the symbol cache.

        Args:
            symbol: Symbol to look up

        Returns:
            Dictionary with exchange, asset_type, and trading_hours, or None if not found
        """
        try:
            import json
            from pathlib import Path

            # Try to get data directory from settings
            try:
                from ktrdr.config.settings import get_settings

                settings = get_settings()
                data_dir = (
                    Path(settings.data_dir)
                    if hasattr(settings, "data_dir")
                    else Path("data")
                )
            except Exception:
                data_dir = Path("data")

            cache_file = data_dir / "symbol_discovery_cache.json"

            if cache_file.exists():
                with open(cache_file) as f:
                    cache_data = json.load(f)

                symbol_info = cache_data.get("cache", {}).get(symbol)
                if symbol_info:
                    return {
                        "exchange": symbol_info.get("exchange"),
                        "asset_type": symbol_info.get("asset_type"),
                        "trading_hours": symbol_info.get("trading_hours"),
                    }
        except Exception as e:
            logger.debug(f"Could not load symbol trading hours from cache: {e}")

        return None


# Convenience functions for backward compatibility
def ensure_utc_timestamp(dt: Union[datetime, pd.Timestamp, str]) -> pd.Timestamp:
    """Convenience function - alias for TimestampManager.to_utc()."""
    return TimestampManager.to_utc(dt)


def format_exchange_time(utc_timestamp: pd.Timestamp, exchange_tz: str) -> str:
    """Convenience function - alias for TimestampManager.format_for_display()."""
    return TimestampManager.format_for_display(utc_timestamp, exchange_tz)
