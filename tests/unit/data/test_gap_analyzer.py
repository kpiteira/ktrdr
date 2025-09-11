"""
Test suite for GapAnalyzer component.

Tests the extracted gap analysis logic to ensure identical behavior
to the original DataManager implementation across all modes.
"""

from datetime import datetime, timezone
from unittest.mock import Mock

import pandas as pd
import pytest

from ktrdr.data.components.gap_analyzer import GapAnalyzer
from ktrdr.data.components.gap_classifier import (
    GapClassification,
    GapClassifier,
    GapInfo,
)


class TestGapAnalyzer:
    """Test suite for GapAnalyzer component."""

    @pytest.fixture
    def gap_classifier(self):
        """Mock GapClassifier for testing."""
        classifier = Mock(spec=GapClassifier)
        # Default mock behavior for gaps that should be filled
        classifier.analyze_gap.return_value = GapInfo(
            start_time=datetime(2023, 1, 1),
            end_time=datetime(2023, 1, 2),
            classification=GapClassification.UNEXPECTED,
            bars_missing=24,
            duration_hours=24.0,
            day_context="weekday",
            note="Mock gap",
        )
        return classifier

    @pytest.fixture
    def gap_analyzer(self, gap_classifier):
        """Create GapAnalyzer instance for testing."""
        return GapAnalyzer(gap_classifier=gap_classifier)

    @pytest.fixture
    def sample_data(self):
        """Create sample OHLC data for testing."""
        dates = pd.date_range("2023-01-01", "2023-01-10", freq="1h", tz="UTC")
        return pd.DataFrame(
            {
                "open": [100.0] * len(dates),
                "high": [101.0] * len(dates),
                "low": [99.0] * len(dates),
                "close": [100.5] * len(dates),
                "volume": [1000] * len(dates),
            },
            index=dates,
        )

    def test_analyze_gaps_no_existing_data(self, gap_analyzer):
        """Test gap analysis when no existing data is available."""
        # This should fail initially since GapAnalyzer doesn't exist yet
        start = datetime(2023, 1, 1, tzinfo=timezone.utc)
        end = datetime(2023, 1, 10, tzinfo=timezone.utc)

        gaps = gap_analyzer.analyze_gaps(
            existing_data=None,
            requested_start=start,
            requested_end=end,
            timeframe="1h",
            symbol="AAPL",
            mode="full",
        )

        # Should return entire range as one gap
        assert len(gaps) == 1
        assert gaps[0] == (start, end)

    def test_analyze_gaps_local_mode(self, gap_analyzer, sample_data):
        """Test that local mode returns no gaps."""
        start = datetime(2023, 1, 1, tzinfo=timezone.utc)
        end = datetime(2023, 1, 10, tzinfo=timezone.utc)

        gaps = gap_analyzer.analyze_gaps(
            existing_data=sample_data,
            requested_start=start,
            requested_end=end,
            timeframe="1h",
            symbol="AAPL",
            mode="local",
        )

        # Local mode should return no gaps
        assert gaps == []

    def test_analyze_gaps_tail_mode(self, gap_analyzer, sample_data):
        """Test tail mode gap analysis."""
        # Request data beyond existing range
        start = datetime(2023, 1, 5, tzinfo=timezone.utc)  # Within existing
        end = datetime(2023, 1, 15, tzinfo=timezone.utc)  # Beyond existing

        gaps = gap_analyzer.analyze_gaps(
            existing_data=sample_data,
            requested_start=start,
            requested_end=end,
            timeframe="1h",
            symbol="AAPL",
            mode="tail",
        )

        # Should find gap after existing data
        assert len(gaps) >= 1
        # Last gap should extend to end date
        assert gaps[-1][1] == end

    def test_analyze_gaps_backfill_mode(self, gap_analyzer, sample_data):
        """Test backfill mode gap analysis."""
        # Request data before existing range
        start = datetime(2022, 12, 20, tzinfo=timezone.utc)  # Before existing
        end = datetime(2023, 1, 5, tzinfo=timezone.utc)  # Within existing

        gaps = gap_analyzer.analyze_gaps(
            existing_data=sample_data,
            requested_start=start,
            requested_end=end,
            timeframe="1h",
            symbol="AAPL",
            mode="backfill",
        )

        # Should find gap before existing data
        assert len(gaps) >= 1
        # First gap should start from start date
        assert gaps[0][0] == start

    def test_analyze_gaps_full_mode(self, gap_analyzer, sample_data):
        """Test full mode gap analysis."""
        # Request data that spans beyond existing range on both sides
        start = datetime(2022, 12, 20, tzinfo=timezone.utc)  # Before existing
        end = datetime(2023, 1, 15, tzinfo=timezone.utc)  # After existing

        gaps = gap_analyzer.analyze_gaps(
            existing_data=sample_data,
            requested_start=start,
            requested_end=end,
            timeframe="1h",
            symbol="AAPL",
            mode="full",
        )

        # Should find gaps before and after existing data
        assert len(gaps) >= 2

    def test_find_internal_gaps(self, gap_analyzer):
        """Test finding gaps within existing data."""
        # Create data with a gap in the middle
        dates1 = pd.date_range("2023-01-01", "2023-01-03", freq="1h", tz="UTC")
        dates2 = pd.date_range("2023-01-05", "2023-01-07", freq="1h", tz="UTC")
        all_dates = dates1.tolist() + dates2.tolist()

        data_with_gap = pd.DataFrame(
            {
                "open": [100.0] * len(all_dates),
                "high": [101.0] * len(all_dates),
                "low": [99.0] * len(all_dates),
                "close": [100.5] * len(all_dates),
                "volume": [1000] * len(all_dates),
            },
            index=pd.DatetimeIndex(all_dates),
        )

        range_start = datetime(2023, 1, 1, tzinfo=timezone.utc)
        range_end = datetime(2023, 1, 7, tzinfo=timezone.utc)

        gaps = gap_analyzer._find_internal_gaps(
            data=data_with_gap,
            range_start=range_start,
            range_end=range_end,
            timeframe="1h",
        )

        # Should find the gap between Jan 3 and Jan 5
        assert len(gaps) >= 1

    def test_is_meaningful_gap(self, gap_analyzer):
        """Test meaningful gap determination."""
        # Small gap - should not be meaningful
        gap_start = datetime(2023, 1, 1, 10, 0, tzinfo=timezone.utc)
        gap_end = datetime(2023, 1, 1, 10, 30, tzinfo=timezone.utc)  # 30 minutes

        is_meaningful = gap_analyzer._is_meaningful_gap(gap_start, gap_end, "1h")
        assert not is_meaningful  # 30 minutes is too small for 1h timeframe

        # Large gap - should be meaningful
        gap_start = datetime(2023, 1, 1, 10, 0, tzinfo=timezone.utc)
        gap_end = datetime(2023, 1, 1, 18, 0, tzinfo=timezone.utc)  # 8 hours

        is_meaningful = gap_analyzer._is_meaningful_gap(gap_start, gap_end, "1h")
        assert is_meaningful  # 8 hours is meaningful for 1h timeframe

    def test_gap_contains_trading_days(self, gap_analyzer):
        """Test trading days detection in gaps."""
        # Weekend gap (Saturday to Sunday) - no trading days
        weekend_start = datetime(2023, 1, 7, tzinfo=timezone.utc)  # Saturday
        weekend_end = datetime(2023, 1, 8, tzinfo=timezone.utc)  # Sunday

        contains_trading = gap_analyzer._gap_contains_trading_days(
            weekend_start, weekend_end
        )
        assert not contains_trading

        # Weekday gap (Monday to Tuesday) - contains trading days
        weekday_start = datetime(2023, 1, 2, tzinfo=timezone.utc)  # Monday
        weekday_end = datetime(2023, 1, 3, tzinfo=timezone.utc)  # Tuesday

        contains_trading = gap_analyzer._gap_contains_trading_days(
            weekday_start, weekday_end
        )
        assert contains_trading

    def test_timezone_consistency(self, gap_analyzer):
        """Test that timezone handling is consistent."""
        # Create data with naive timestamps
        dates = pd.date_range("2023-01-01", "2023-01-10", freq="1h")  # Naive
        naive_data = pd.DataFrame(
            {
                "open": [100.0] * len(dates),
                "high": [101.0] * len(dates),
                "low": [99.0] * len(dates),
                "close": [100.5] * len(dates),
                "volume": [1000] * len(dates),
            },
            index=dates,
        )

        # Analyze with timezone-aware request
        start = datetime(2023, 1, 5, tzinfo=timezone.utc)
        end = datetime(2023, 1, 15, tzinfo=timezone.utc)

        # Should handle timezone conversion properly
        gaps = gap_analyzer.analyze_gaps(
            existing_data=naive_data,
            requested_start=start,
            requested_end=end,
            timeframe="1h",
            symbol="AAPL",
            mode="full",
        )

        # Should not crash and should return valid gaps
        assert isinstance(gaps, list)

    def test_large_gap_handling(self, gap_analyzer, gap_classifier):
        """Test that large gaps (>7 days) are always considered for filling."""
        # Mock classifier to return expected gap (would normally skip)
        gap_classifier.analyze_gap.return_value = GapInfo(
            start_time=datetime(2023, 1, 1),
            end_time=datetime(2023, 1, 15),  # 14 days
            classification=GapClassification.EXPECTED_WEEKEND,  # Would normally skip
            bars_missing=336,
            duration_hours=336.0,
            day_context="weekend",
            note="Large gap test",
        )

        start = datetime(2023, 1, 1, tzinfo=timezone.utc)
        end = datetime(2023, 1, 15, tzinfo=timezone.utc)

        gaps = gap_analyzer.analyze_gaps(
            existing_data=None,
            requested_start=start,
            requested_end=end,
            timeframe="1h",
            symbol="AAPL",
            mode="full",
        )

        # Large gap should be included despite being "expected"
        assert len(gaps) == 1
        assert gaps[0] == (start, end)

    def test_mode_parameter_compatibility(self, gap_analyzer, sample_data):
        """Test that all mode parameters are handled correctly."""
        start = datetime(2022, 12, 20, tzinfo=timezone.utc)
        end = datetime(2023, 1, 15, tzinfo=timezone.utc)

        modes = ["local", "tail", "backfill", "full"]

        for mode in modes:
            gaps = gap_analyzer.analyze_gaps(
                existing_data=sample_data,
                requested_start=start,
                requested_end=end,
                timeframe="1h",
                symbol="AAPL",
                mode=mode,
            )

            # All modes should return valid results
            assert isinstance(gaps, list)

            # Local mode should return empty
            if mode == "local":
                assert gaps == []
            # Other modes should find gaps
            else:
                # Will vary by mode but should be deterministic
                assert isinstance(gaps, list)

    def test_safeguard_missing_trading_hours(self, gap_analyzer):
        """Test safeguard that skips gaps <2 days when trading hours data is missing."""
        # Create test data with a clear gap in the middle
        timestamps = pd.date_range(
            "2024-01-01 10:00", "2024-01-01 20:00", freq="1h", tz="UTC"
        )

        # Create data with gap in middle (remove hours 14-16 to create 3-hour gap)
        data_timestamps = timestamps[
            [0, 1, 2, 3, 4, 7, 8, 9, 10]
        ]  # Skip indices 5,6 for gap
        test_data = pd.DataFrame(
            {"close": list(range(100, 109))}, index=data_timestamps
        )

        # Mock the gap_classifier to simulate missing trading hours
        gap_analyzer.gap_classifier.symbol_metadata = {}  # No trading hours data

        # Test with symbol that has no trading hours data (like MSFT in the issue)
        gaps = gap_analyzer.analyze_gaps(
            test_data,
            timestamps[0],
            timestamps[-1],
            "UNKNOWN_SYMBOL",
            "1h",
            mode="tail",
        )

        # Should find no gaps due to safeguard (gap is <2 days and no trading hours)
        assert len(gaps) == 0

        # Test with large gap (>7 days) - should still be filled even without trading hours
        large_start = pd.Timestamp("2024-01-01 10:00", tz="UTC")
        large_end = pd.Timestamp("2024-01-10 10:00", tz="UTC")  # 9 days later

        test_data_large = pd.DataFrame(
            {"close": [100, 101]}, index=[large_start, large_end]
        )

        gaps_large = gap_analyzer.analyze_gaps(
            test_data_large, large_start, large_end, "UNKNOWN_SYMBOL", "1h", mode="tail"
        )

        # Should find the large gap (>7 days rule overrides safeguard)
        assert len(gaps_large) == 1


class TestGapAnalyzerIntegration:
    """Integration tests for GapAnalyzer with DataManager."""

    def test_datamanager_integration(self):
        """Test that GapAnalyzer integrates properly with DataManager."""
        # This test will verify that DataManager can use GapAnalyzer
        # instead of its internal gap analysis methods

        from ktrdr.data.data_manager import DataManager

        dm = DataManager()

        # DataManager should now have a gap_analyzer component
        assert hasattr(dm, "gap_analyzer")
        assert dm.gap_analyzer is not None
        assert hasattr(dm.gap_analyzer, "analyze_gaps")



if __name__ == "__main__":
    pytest.main([__file__])
