"""
Tests for timezone utilities.

This module tests the TimestampManager class and related timezone handling utilities.
"""

import pytest
from datetime import datetime
import pandas as pd
import pytz
from unittest.mock import patch

from ktrdr.utils.timezone_utils import (
    TimestampManager,
    ensure_utc_timestamp,
    format_exchange_time,
)


class TestTimestampManager:
    """Test suite for TimestampManager."""

    def test_to_utc_with_none(self):
        """Test to_utc with None input."""
        result = TimestampManager.to_utc(None)
        assert result is None

    def test_to_utc_with_string(self):
        """Test to_utc with string input."""
        result = TimestampManager.to_utc("2025-06-07 15:30:00")
        assert isinstance(result, pd.Timestamp)
        assert str(result.tz) == "UTC"
        assert result.hour == 15
        assert result.minute == 30

    def test_to_utc_with_datetime(self):
        """Test to_utc with datetime input."""
        dt = datetime(2025, 6, 7, 15, 30, 0)
        result = TimestampManager.to_utc(dt)
        assert isinstance(result, pd.Timestamp)
        assert str(result.tz) == "UTC"

    def test_to_utc_with_naive_timestamp(self):
        """Test to_utc with timezone-naive pandas timestamp."""
        ts = pd.Timestamp("2025-06-07 15:30:00")
        result = TimestampManager.to_utc(ts)
        assert str(result.tz) == "UTC"
        assert result.hour == 15

    def test_to_utc_with_aware_timestamp_utc(self):
        """Test to_utc with UTC timezone-aware timestamp."""
        ts = pd.Timestamp("2025-06-07 15:30:00", tz="UTC")
        result = TimestampManager.to_utc(ts)
        assert str(result.tz) == "UTC"
        assert result.hour == 15
        assert result == ts  # Should be unchanged

    def test_to_utc_with_aware_timestamp_est(self):
        """Test to_utc with EST timezone-aware timestamp."""
        # 3:30 PM EST = 8:30 PM UTC (during standard time)
        est_tz = pytz.timezone("America/New_York")
        ts = pd.Timestamp("2025-01-07 15:30:00")  # January for EST
        ts_est = ts.tz_localize(est_tz)
        result = TimestampManager.to_utc(ts_est)

        assert str(result.tz) == "UTC"
        # EST is UTC-5, so 15:30 EST = 20:30 UTC
        assert result.hour == 20
        assert result.minute == 30

    def test_to_utc_with_invalid_string(self):
        """Test to_utc with invalid string format."""
        with pytest.raises(ValueError, match="Invalid datetime format"):
            TimestampManager.to_utc("invalid-date-format")

    def test_to_exchange_time_success(self):
        """Test converting UTC to exchange timezone."""
        utc_ts = pd.Timestamp("2025-06-07 20:30:00", tz="UTC")
        est_result = TimestampManager.to_exchange_time(utc_ts, "America/New_York")

        # June: EDT (UTC-4), so 20:30 UTC = 16:30 EDT
        assert est_result.hour == 16
        assert est_result.minute == 30

    def test_to_exchange_time_with_none(self):
        """Test to_exchange_time with None input."""
        with pytest.raises(ValueError, match="UTC timestamp cannot be None"):
            TimestampManager.to_exchange_time(None, "America/New_York")

    def test_to_exchange_time_with_non_utc(self):
        """Test to_exchange_time with non-UTC timestamp."""
        est_ts = pd.Timestamp("2025-06-07 15:30:00", tz="America/New_York")
        with pytest.raises(ValueError, match="Expected UTC timestamp"):
            TimestampManager.to_exchange_time(est_ts, "America/New_York")

    def test_to_exchange_time_with_invalid_timezone(self):
        """Test to_exchange_time with invalid timezone."""
        utc_ts = pd.Timestamp("2025-06-07 20:30:00", tz="UTC")
        with pytest.raises(ValueError, match="Invalid exchange timezone"):
            TimestampManager.to_exchange_time(utc_ts, "Invalid/Timezone")

    def test_format_for_display_utc(self):
        """Test formatting for UTC display."""
        utc_ts = pd.Timestamp("2025-06-07 15:30:00", tz="UTC")
        result = TimestampManager.format_for_display(utc_ts, "UTC")
        assert result == "2025-06-07 15:30:00 UTC"

    def test_format_for_display_exchange_timezone(self):
        """Test formatting for exchange timezone display."""
        utc_ts = pd.Timestamp("2025-06-07 20:30:00", tz="UTC")
        result = TimestampManager.format_for_display(utc_ts, "America/New_York")
        assert "2025-06-07 16:30:00" in result
        assert "EDT" in result or "EST" in result  # Depends on date

    def test_format_for_display_with_none(self):
        """Test formatting with None input."""
        result = TimestampManager.format_for_display(None)
        assert result == "N/A"

    def test_convert_dataframe_index(self):
        """Test converting DataFrame index to UTC."""
        # Create DataFrame with timezone-naive index
        dates = pd.date_range("2025-06-07 15:00:00", periods=3, freq="1h")
        df = pd.DataFrame({"value": [1, 2, 3]}, index=dates)

        result = TimestampManager.convert_dataframe_index(df)

        assert isinstance(result.index, pd.DatetimeIndex)
        assert str(result.index.tz) == "UTC"
        assert len(result) == 3
        assert not result.equals(df)  # Should be a copy

    def test_convert_dataframe_index_with_aware_index(self):
        """Test converting DataFrame with timezone-aware index."""
        # Create DataFrame with EST timezone-aware index
        dates = pd.date_range(
            "2025-01-07 15:00:00", periods=3, freq="1h", tz="America/New_York"
        )
        df = pd.DataFrame({"value": [1, 2, 3]}, index=dates)

        result = TimestampManager.convert_dataframe_index(df)

        assert str(result.index.tz) == "UTC"
        # EST is UTC-5, so 15:00 EST = 20:00 UTC
        assert result.index[0].hour == 20

    def test_convert_dataframe_index_empty(self):
        """Test converting empty DataFrame."""
        df = pd.DataFrame()
        result = TimestampManager.convert_dataframe_index(df)
        assert result.empty

    def test_convert_dataframe_index_invalid(self):
        """Test converting DataFrame without datetime index."""
        df = pd.DataFrame({"value": [1, 2, 3]}, index=[0, 1, 2])
        with pytest.raises(ValueError, match="DataFrame must have a DatetimeIndex"):
            TimestampManager.convert_dataframe_index(df)

    def test_to_utc_series(self):
        """Test converting DatetimeIndex series to UTC."""
        # Timezone-naive series
        dates = pd.date_range("2025-06-07 15:00:00", periods=3, freq="1h")
        result = TimestampManager.to_utc_series(dates)
        assert str(result.tz) == "UTC"

        # Timezone-aware series (EST)
        dates_est = pd.date_range(
            "2025-01-07 15:00:00", periods=3, freq="1h", tz="America/New_York"
        )
        result_est = TimestampManager.to_utc_series(dates_est)
        assert str(result_est.tz) == "UTC"
        assert result_est[0].hour == 20  # 15:00 EST = 20:00 UTC

    def test_validate_timezone_consistency_success(self):
        """Test timezone validation with valid UTC DataFrame."""
        dates = pd.date_range("2025-06-07 15:00:00", periods=3, freq="1h", tz="UTC")
        df = pd.DataFrame({"value": [1, 2, 3]}, index=dates)

        # Should not raise an exception
        TimestampManager.validate_timezone_consistency(df, "test_operation")

    def test_validate_timezone_consistency_empty(self):
        """Test timezone validation with empty DataFrame."""
        df = pd.DataFrame()
        # Should not raise an exception
        TimestampManager.validate_timezone_consistency(df, "test_operation")

    def test_validate_timezone_consistency_none(self):
        """Test timezone validation with None."""
        # Should not raise an exception
        TimestampManager.validate_timezone_consistency(None, "test_operation")

    def test_validate_timezone_consistency_no_datetime_index(self):
        """Test timezone validation with non-datetime index."""
        df = pd.DataFrame({"value": [1, 2, 3]}, index=[0, 1, 2])
        with pytest.raises(
            ValueError, match="test_operation: DataFrame must have a DatetimeIndex"
        ):
            TimestampManager.validate_timezone_consistency(df, "test_operation")

    def test_validate_timezone_consistency_naive_index(self):
        """Test timezone validation with timezone-naive index."""
        dates = pd.date_range("2025-06-07 15:00:00", periods=3, freq="1h")
        df = pd.DataFrame({"value": [1, 2, 3]}, index=dates)
        with pytest.raises(
            ValueError, match="test_operation: DataFrame has timezone-naive index"
        ):
            TimestampManager.validate_timezone_consistency(df, "test_operation")

    def test_validate_timezone_consistency_non_utc(self):
        """Test timezone validation with non-UTC timezone."""
        dates = pd.date_range(
            "2025-06-07 15:00:00", periods=3, freq="1h", tz="America/New_York"
        )
        df = pd.DataFrame({"value": [1, 2, 3]}, index=dates)
        with pytest.raises(
            ValueError, match="test_operation: DataFrame has non-UTC timezone"
        ):
            TimestampManager.validate_timezone_consistency(df, "test_operation")

    def test_now_utc(self):
        """Test getting current UTC timestamp."""
        result = TimestampManager.now_utc()
        assert isinstance(result, pd.Timestamp)
        assert str(result.tz) == "UTC"

    def test_is_market_hours_weekday_regular(self):
        """Test market hours check during regular trading hours."""
        # 2:30 PM EST on a Tuesday = 19:30 UTC
        utc_ts = pd.Timestamp("2025-06-10 19:30:00", tz="UTC")  # Tuesday
        result = TimestampManager.is_market_hours(utc_ts)
        assert result is True

    def test_is_market_hours_weekday_before_open(self):
        """Test market hours check before market open."""
        # 8:00 AM EST on a Tuesday = 13:00 UTC
        utc_ts = pd.Timestamp("2025-06-10 13:00:00", tz="UTC")  # Tuesday
        result = TimestampManager.is_market_hours(utc_ts)
        assert result is False

    def test_is_market_hours_weekday_after_close(self):
        """Test market hours check after market close."""
        # 5:00 PM EST on a Tuesday = 22:00 UTC
        utc_ts = pd.Timestamp("2025-06-10 22:00:00", tz="UTC")  # Tuesday
        result = TimestampManager.is_market_hours(utc_ts)
        assert result is False

    def test_is_market_hours_weekend(self):
        """Test market hours check on weekend."""
        # Saturday
        utc_ts = pd.Timestamp("2025-06-07 19:30:00", tz="UTC")  # Saturday
        result = TimestampManager.is_market_hours(utc_ts)
        assert result is False

    def test_get_trading_session_regular(self):
        """Test trading session detection - regular hours."""
        # 2:30 PM EST on a Tuesday = 19:30 UTC
        utc_ts = pd.Timestamp("2025-06-10 19:30:00", tz="UTC")  # Tuesday
        result = TimestampManager.get_trading_session(utc_ts)
        assert result == "regular"

    def test_get_trading_session_pre_market(self):
        """Test trading session detection - pre-market."""
        # 8:00 AM EST on a Tuesday = 13:00 UTC
        utc_ts = pd.Timestamp("2025-06-10 13:00:00", tz="UTC")  # Tuesday
        result = TimestampManager.get_trading_session(utc_ts)
        assert result == "pre_market"

    def test_get_trading_session_after_hours(self):
        """Test trading session detection - after hours."""
        # 6:00 PM EST on a Tuesday = 23:00 UTC
        utc_ts = pd.Timestamp("2025-06-10 23:00:00", tz="UTC")  # Tuesday
        result = TimestampManager.get_trading_session(utc_ts)
        assert result == "after_hours"

    def test_get_trading_session_closed(self):
        """Test trading session detection - closed (weekend)."""
        # Saturday
        utc_ts = pd.Timestamp("2025-06-07 19:30:00", tz="UTC")  # Saturday
        result = TimestampManager.get_trading_session(utc_ts)
        assert result == "closed"

    def test_get_trading_session_late_night(self):
        """Test trading session detection - late night/early morning."""
        # 2:00 AM EST on a Tuesday = 07:00 UTC
        utc_ts = pd.Timestamp("2025-06-10 07:00:00", tz="UTC")  # Tuesday
        result = TimestampManager.get_trading_session(utc_ts)
        assert result == "closed"


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_ensure_utc_timestamp(self):
        """Test ensure_utc_timestamp convenience function."""
        dt = datetime(2025, 6, 7, 15, 30, 0)
        result = ensure_utc_timestamp(dt)
        assert isinstance(result, pd.Timestamp)
        assert str(result.tz) == "UTC"

    def test_format_exchange_time(self):
        """Test format_exchange_time convenience function."""
        utc_ts = pd.Timestamp("2025-06-07 20:30:00", tz="UTC")
        result = format_exchange_time(utc_ts, "America/New_York")
        assert "2025-06-07 16:30:00" in result


class TestErrorHandling:
    """Test error handling and edge cases."""

    @patch("ktrdr.utils.timezone_utils.logger")
    def test_to_utc_logging_on_conversion(self, mock_logger):
        """Test that timezone conversions are logged."""
        # Test timezone-naive conversion
        TimestampManager.to_utc("2025-06-07 15:30:00")
        mock_logger.debug.assert_called()

    @patch("ktrdr.utils.timezone_utils.logger")
    def test_error_handling_with_logging(self, mock_logger):
        """Test that errors are properly logged."""
        # This should trigger error logging
        with pytest.raises(ValueError):
            TimestampManager.to_utc("invalid-format")
        mock_logger.error.assert_called()

    def test_market_hours_with_error(self):
        """Test market hours check with invalid timezone."""
        utc_ts = pd.Timestamp("2025-06-07 15:30:00", tz="UTC")
        # Should return False and log warning for invalid timezone
        result = TimestampManager.is_market_hours(utc_ts, "Invalid/Timezone")
        assert result is False

    def test_trading_session_with_error(self):
        """Test trading session with invalid timezone."""
        utc_ts = pd.Timestamp("2025-06-07 15:30:00", tz="UTC")
        # Should return 'unknown' and log warning for invalid timezone
        result = TimestampManager.get_trading_session(utc_ts, "Invalid/Timezone")
        assert result == "unknown"
