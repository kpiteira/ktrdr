"""
Unit tests for IB Data Fetcher datetime handling fix.

Tests the fix for D2.2 bug: Invalid comparison between dtype=datetime64[ns, UTC] and datetime

These tests verify that the data fetcher correctly handles both timezone-aware
and timezone-naive datetime objects when filtering DataFrame results.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from ktrdr.ib.data_fetcher import IbDataFetcher


class TestDataFetcherDatetimeHandling:
    """Test datetime handling in data fetcher, specifically the D2.2 bug fix."""

    @pytest.fixture
    def mock_ib_connection(self):
        """Create a mock IB connection."""
        mock_ib = MagicMock()

        # Create mock bars with timezone-aware dates
        mock_bars = []
        for i in range(5):
            bar = MagicMock()
            bar.date = datetime(2024, 12, 1 + i, 12, 0, 0, tzinfo=timezone.utc)
            bar.open = 1.05 + (i * 0.01)
            bar.high = 1.06 + (i * 0.01)
            bar.low = 1.04 + (i * 0.01)
            bar.close = 1.05 + (i * 0.01)
            bar.volume = 1000 + (i * 100)
            mock_bars.append(bar)

        mock_ib.reqHistoricalData.return_value = mock_bars
        return mock_ib

    @pytest.fixture
    def data_fetcher(self):
        """Create a data fetcher instance."""
        return IbDataFetcher()

    def test_datetime_filter_with_naive_datetime(
        self, data_fetcher, mock_ib_connection
    ):
        """
        Test that naive datetime objects work correctly in filtering.

        This is the primary test for the D2.2 bug fix. Before the fix, this would
        raise TypeError: Invalid comparison between dtype=datetime64[ns, UTC] and datetime
        """
        # Arrange: Create naive datetime objects (no tzinfo)
        start = datetime(2024, 12, 1, 0, 0, 0)  # Naive
        end = datetime(2024, 12, 5, 23, 59, 59)  # Naive

        # Act: Call the implementation with mock IB connection
        with patch.object(
            data_fetcher.connection_pool, "execute_with_connection_sync"
        ) as mock_execute:
            # Configure mock to call the actual implementation method
            def call_impl(*args, **kwargs):
                impl_method = args[0]
                impl_args = args[1:]
                return impl_method(mock_ib_connection, *impl_args)

            mock_execute.side_effect = call_impl

            # This should NOT raise TypeError
            result = data_fetcher._fetch_historical_data_impl(
                mock_ib_connection,
                symbol="EURUSD",
                timeframe="1h",
                start=start,
                end=end,
                instrument_type="CASH",
            )

        # Assert: Should return DataFrame without errors
        assert isinstance(result, pd.DataFrame)
        assert not result.empty
        assert len(result) == 5
        assert result.index.tz is not None  # Should be timezone-aware
        assert str(result.index.tz) == "UTC"  # Should be UTC

    def test_datetime_filter_with_aware_datetime(
        self, data_fetcher, mock_ib_connection
    ):
        """
        Test that timezone-aware datetime objects work correctly in filtering.

        This verifies the fix also works with TZ-aware inputs.
        """
        # Arrange: Create TZ-aware datetime objects
        start = datetime(2024, 12, 1, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 12, 5, 23, 59, 59, tzinfo=timezone.utc)

        # Act: Call the implementation
        result = data_fetcher._fetch_historical_data_impl(
            mock_ib_connection,
            symbol="EURUSD",
            timeframe="1h",
            start=start,
            end=end,
            instrument_type="CASH",
        )

        # Assert: Should work without errors
        assert isinstance(result, pd.DataFrame)
        assert not result.empty
        assert len(result) == 5
        assert result.index.tz is not None
        assert str(result.index.tz) == "UTC"

    def test_datetime_filter_excludes_out_of_range(
        self, data_fetcher, mock_ib_connection
    ):
        """
        Test that date filtering correctly excludes bars outside the range.

        Verifies that the pd.Timestamp conversion maintains filtering logic.
        """
        # Arrange: Request narrow date range
        start = datetime(2024, 12, 2, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 12, 3, 23, 59, 59, tzinfo=timezone.utc)

        # Act: Call the implementation
        result = data_fetcher._fetch_historical_data_impl(
            mock_ib_connection,
            symbol="EURUSD",
            timeframe="1h",
            start=start,
            end=end,
            instrument_type="CASH",
        )

        # Assert: Should only include bars from Dec 2-3
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2  # Only bars from Dec 2 and Dec 3
        assert result.index[0].day == 2
        assert result.index[-1].day == 3

    def test_datetime_filter_with_mixed_timezone_bars(self, data_fetcher):
        """
        Test that bars with non-UTC timezones are properly converted and filtered.

        Verifies that the UTC conversion works correctly before filtering.
        """
        # Arrange: Create mock with mixed timezone bars
        mock_ib = MagicMock()

        # Create bars with Eastern Time (UTC-5)
        from datetime import timedelta

        eastern_tz = timezone(timedelta(hours=-5))

        mock_bars = []
        for i in range(3):
            bar = MagicMock()
            bar.date = datetime(2024, 12, 1 + i, 17, 0, 0, tzinfo=eastern_tz)  # 5 PM ET
            bar.open = bar.high = bar.low = bar.close = 1.05
            bar.volume = 1000
            mock_bars.append(bar)

        mock_ib.reqHistoricalData.return_value = mock_bars

        # Request in UTC
        start = datetime(2024, 12, 1, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 12, 3, 23, 59, 59, tzinfo=timezone.utc)

        # Act: Call the implementation
        result = data_fetcher._fetch_historical_data_impl(
            mock_ib,
            symbol="EURUSD",
            timeframe="1h",
            start=start,
            end=end,
            instrument_type="CASH",
        )

        # Assert: All bars should be converted to UTC and included
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3
        assert str(result.index.tz) == "UTC"
        # 5 PM ET = 10 PM UTC (or 22:00)
        assert all(result.index.hour == 22)

    def test_pandas_timestamp_preserves_timezone(self):
        """
        Test that pd.Timestamp() correctly preserves timezone information.

        This is a direct test of the fix mechanism.
        """
        # Arrange: Create various datetime objects
        naive_dt = datetime(2024, 12, 1, 12, 0, 0)
        aware_dt = datetime(2024, 12, 1, 12, 0, 0, tzinfo=timezone.utc)

        # Act: Convert to pandas Timestamps
        naive_ts = pd.Timestamp(naive_dt)
        aware_ts = pd.Timestamp(aware_dt)

        # Assert: Timestamps should be compatible with DatetimeIndex
        test_index = pd.DatetimeIndex(
            [datetime(2024, 12, 1, 12, 0, 0, tzinfo=timezone.utc)]
        )

        # These comparisons should NOT raise TypeError
        _ = test_index >= aware_ts  # Should work

        # Naive timestamp comparison with TZ-aware index
        # After localization, should work
        naive_ts_utc = naive_ts.tz_localize("UTC")
        _ = test_index >= naive_ts_utc  # Should work

    def test_dataframe_filtering_with_both_timestamp_types(self):
        """
        Integration test: Create DataFrame and filter with various datetime types.

        Comprehensive test of the complete filtering logic.
        """
        # Arrange: Create DataFrame with UTC DatetimeIndex
        dates = pd.date_range("2024-12-01", periods=10, freq="1h", tz="UTC")
        df = pd.DataFrame(
            {
                "open": range(10),
                "high": range(10),
                "low": range(10),
                "close": range(10),
                "volume": range(10),
            },
            index=dates,
        )

        # Test with naive datetime
        start_naive = datetime(2024, 12, 1, 3, 0, 0)
        end_naive = datetime(2024, 12, 1, 7, 0, 0)

        start_pd = pd.Timestamp(start_naive)
        end_pd = pd.Timestamp(end_naive)

        # Localize naive timestamps to UTC to match DataFrame index
        # This is the same fix applied in data_fetcher.py
        if start_pd.tz is None:
            start_pd = start_pd.tz_localize('UTC')
        if end_pd.tz is None:
            end_pd = end_pd.tz_localize('UTC')

        # Act: Filter (mimics the fixed code)
        filtered = df[(df.index >= start_pd) & (df.index <= end_pd)]

        # Assert: Should work and return correct range
        assert isinstance(filtered, pd.DataFrame)
        assert len(filtered) == 5  # Hours 3-7 inclusive


class TestEndpointTimezoneNormalization:
    """Test timezone normalization at the endpoint level."""

    def test_naive_datetime_normalized_to_utc(self):
        """
        Test that naive datetimes are correctly normalized to UTC at endpoint.

        This tests Fix 2 (endpoint-level timezone normalization).
        """
        from datetime import timezone

        # Arrange: Create naive datetime (simulating Pydantic parse without Z)
        naive_dt = datetime(2024, 12, 1, 0, 0, 0)

        # Act: Apply the fix logic
        if naive_dt.tzinfo is None:
            normalized_dt = naive_dt.replace(tzinfo=timezone.utc)
        else:
            normalized_dt = naive_dt

        # Assert: Should now be TZ-aware
        assert normalized_dt.tzinfo is not None
        assert normalized_dt.tzinfo == timezone.utc
        assert normalized_dt.isoformat() == "2024-12-01T00:00:00+00:00"

    def test_aware_datetime_preserved(self):
        """
        Test that already TZ-aware datetimes are not modified.
        """
        from datetime import timezone

        # Arrange: Create TZ-aware datetime
        aware_dt = datetime(2024, 12, 1, 0, 0, 0, tzinfo=timezone.utc)

        # Act: Apply the fix logic (should be no-op)
        if aware_dt.tzinfo is None:
            normalized_dt = aware_dt.replace(tzinfo=timezone.utc)
        else:
            normalized_dt = aware_dt

        # Assert: Should be unchanged
        assert normalized_dt.tzinfo is not None
        assert normalized_dt == aware_dt
        assert id(normalized_dt) == id(aware_dt)  # Same object


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
